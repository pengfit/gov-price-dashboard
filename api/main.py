#!/usr/bin/env python3
"""
gov-price-dashboard API
FastAPI 后端 - 提供建材价格搜索和聚合 API
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from elasticsearch import Elasticsearch
from typing import Optional
import os

ES_HOST = os.environ.get("ES_HOST", "http://localhost:59200")
ES_INDEX = os.environ.get("ES_INDEX", "gov_price_index")

app = FastAPI(title="gov-price-dashboard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

es = Elasticsearch([ES_HOST])


def _build_bool_query(must_clauses, filter_clauses):
    """构建 bool 查询，处理空列表情况"""
    must_clause = must_clauses if must_clauses else [{"match_all": {}}]
    if filter_clauses:
        return {"bool": {"must": must_clause, "filter": filter_clauses}}
    return {"bool": {"must": must_clause}}


@app.get("/")
def root():
    return {"message": "gov-price-dashboard API", "version": "1.0.0"}


@app.get("/health")
def health():
    try:
        info = es.info()
        return {"status": "ok", "es": info["cluster_name"], "host": ES_HOST}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/search")
def search(
    keyword: Optional[str] = Query(None),
    province: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    county: Optional[str] = Query(None),
    unit: Optional[str] = Query(None),
    price_min: Optional[float] = Query(None),
    price_max: Optional[float] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    must_clauses = []
    filter_clauses = []

    if keyword:
        kw_len = len(keyword)
        if kw_len <= 2:
            # 短词（≤2字符）：精确 keyword 匹配 + 宽松 fuzzy 容错
            must_clauses.append({
                "bool": {
                    "should": [
                        {"term": {"breed.keyword": {"value": keyword, "boost": 15}}},
                        {"match": {"breed": {"query": keyword, "fuzziness": "AUTO", "boost": 5}}},
                    ]
                }
            })
        else:
            # 较长词（≥3字符）：严格 AND 匹配 + 短句精确匹配
            # 不用 fuzzy：中文单字拆词后 fuzzy 太松，容易匹配到无关结果
            must_clauses.append({
                "bool": {
                    "should": [
                        {"match_phrase": {"breed": {"query": keyword, "boost": 20}}},
                        {"match": {"breed": {"query": keyword, "operator": "and", "minimum_should_match": "100%", "boost": 10}}},
                    ]
                }
            })
    if province:
        filter_clauses.append({"term": {"province": province}})
    if city:
        filter_clauses.append({"term": {"city": city}})
    if county:
        filter_clauses.append({"term": {"county": county}})
    if unit:
        filter_clauses.append({"term": {"unit": unit}})
    if price_min is not None and price_max is not None and price_min <= price_max:
        filter_clauses.append({"range": {"price": {"gte": price_min, "lte": price_max}}})
    elif price_min is not None and price_min >= 0:
        filter_clauses.append({"range": {"price": {"gte": price_min}}})
    elif price_max is not None and price_max >= 0:
        filter_clauses.append({"range": {"price": {"lte": price_max}}})

    query = _build_bool_query(must_clauses, filter_clauses)
    from_idx = (page - 1) * page_size

    body = {
        "query": query,
        "from": from_idx,
        "size": page_size,
        "sort": [{"date": {"order": "desc"}}, {"_score": {"order": "desc"}}],
        "aggs": {
            "by_breed_spec": {
                "terms": {
                    "field": "breed.keyword",
                    "size": 10000,
                    "order": {"_count": "desc"}
                },
                "aggs": {
                    "spec_vals": {
                        "terms": {
                            "field": "spec.keyword",
                            "size": 50
                        },
                        "aggs": {
                            "avg_price": {"avg": {"field": "price"}},
                            "avg_tax_price": {"avg": {"field": "tax_price"}}
                        }
                    }
                }
            }
        }
    }

    try:
        result = es.search(index=ES_INDEX, body=body)
        total = result["hits"]["total"]["value"]

        # Build breed→spec→avg lookup from aggregation results
        avg_price_map = {}  # (breed, spec) → avg_price
        try:
            for breed_bucket in result["aggregations"]["by_breed_spec"]["buckets"]:
                breed = breed_bucket["key"]
                for spec_bucket in breed_bucket["spec_vals"]["buckets"]:
                    spec = spec_bucket["key"]
                    avg_price_map[(breed, spec)] = round(spec_bucket["avg_price"]["value"], 2) if spec_bucket["avg_price"]["value"] else 0
        except Exception:
            pass

        # Build prev_month price lookup for (breed, city, province) → prev_price using composite agg
        prev_price_map = {}
        try:
            prev_query = {
                "bool": {
                    "must": query.get("bool", {}).get("must", [{"match_all": {}}]),
                    "filter": query.get("bool", {}).get("filter", []) + [
                        {"range": {"date": {"gte": "now-3M/M", "lt": "now-2M/M"}}}
                    ]
                }
            }
            prev_body = {
                "query": prev_query,
                "size": 0,
                "aggs": {
                    "by_key": {
                        "composite": {
                            "sources": [
                                {"breed": {"terms": {"field": "breed.keyword"}}},
                                {"city": {"terms": {"field": "city"}}},
                                {"province": {"terms": {"field": "province"}}},
                            ],
                            "size": 10000
                        },
                        "aggs": {
                            "avg_price": {"avg": {"field": "price"}}
                        }
                    }
                }
            }
            prev_result = es.search(index=ES_INDEX, body=prev_body)
            for bucket in prev_result["aggregations"]["by_key"]["buckets"]:
                key = bucket["key"]
                if not key.get("breed"):
                    continue
                avg = bucket["avg_price"]["value"]
                if avg:
                    prev_price_map[(key["breed"], key["city"], key["province"])] = round(avg, 2)
        except Exception:
            pass

        hits = [
            {
                "id": h["_id"],
                "breed": h["_source"].get("breed", ""),
                "spec": h["_source"].get("spec", ""),
                "unit": h["_source"].get("unit", ""),
                "price": h["_source"].get("price"),
                "tax_price": h["_source"].get("tax_price"),
                "province": h["_source"].get("province", ""),
                "city": h["_source"].get("city", ""),
                "county": h["_source"].get("county", ""),
                "date": h["_source"].get("date", ""),
                "avg_price": avg_price_map.get((h["_source"].get("breed", ""), h["_source"].get("spec", "")), 0),
                "prev_price": prev_price_map.get((h["_source"].get("breed", ""), h["_source"].get("city", ""), h["_source"].get("province", "")), 0),
            }
            for h in result["hits"]["hits"]
        ]
        return {
            "total": total,
            "page": page,
            "size": page_size,
            "pages": (total + page_size - 1) // page_size,
            "data": hits
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats/overview")
def overview(
    keyword: Optional[str] = Query(None),
    province: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    unit: Optional[str] = Query(None),
):
    must_clauses = []
    filter_clauses = []

    if keyword:
        kw_len = len(keyword)
        if kw_len <= 2:
            must_clauses.append({
                "bool": {
                    "should": [
                        {"term": {"breed.keyword": {"value": keyword, "boost": 15}}},
                        {"match": {"breed": {"query": keyword, "fuzziness": "AUTO", "boost": 5}}},
                        {"match": {"spec": {"query": keyword, "fuzziness": "AUTO", "boost": 3}}},
                    ]
                }
            })
        else:
            must_clauses.append({
                "bool": {
                    "should": [
                        {"match_phrase": {"breed": {"query": keyword, "boost": 20}}},
                        {"match": {"breed": {"query": keyword, "operator": "and", "minimum_should_match": "100%", "boost": 10}}},
                        {"match": {"spec": {"query": keyword, "fuzziness": "AUTO", "boost": 5}}},
                    ]
                }
            })
    if province:
        filter_clauses.append({"term": {"province": province}})
    if city:
        filter_clauses.append({"term": {"city": city}})
    if unit:
        filter_clauses.append({"term": {"unit": unit}})

    query = _build_bool_query(must_clauses, filter_clauses)
    body = {
        "query": query,
        "size": 0,
        "aggs": {
            "provinces": {"cardinality": {"field": "province"}},
            "cities": {"cardinality": {"field": "city"}},
            "avg_price": {"avg": {"field": "price"}},
            "max_price": {"max": {"field": "price"}},
            "min_price": {"min": {"field": "price"}},
            "by_province": {
                "terms": {"field": "province", "size": 30},
                "aggs": {
                    "avg_price": {"avg": {"field": "price"}},
                    "count": {"value_count": {"field": "price"}}
                }
            }
        }
    }
    try:
        # 用 _count API 获取真实总数
        total_result = es.count(index=ES_INDEX, body={"query": query})
        total_docs = total_result["count"]

        result = es.search(index=ES_INDEX, body=body)
        aggs = result["aggregations"]
        province_buckets = aggs["by_province"]["buckets"]
        return {
            "total_docs": total_docs,
            "total_provinces": aggs["provinces"]["value"],
            "total_cities": aggs["cities"]["value"],
            "avg_price": round(aggs["avg_price"]["value"], 2) if aggs["avg_price"]["value"] else 0,
            "max_price": aggs["max_price"]["value"] or 0,
            "min_price": aggs["min_price"]["value"] or 0,
            "by_province": [
                {
                    "province": b["key"],
                    "count": b["count"]["value"],
                    "avg_price": round(b["avg_price"]["value"], 2) if b["avg_price"]["value"] else 0
                }
                for b in province_buckets
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats/top-products")
def top_products(
    limit: int = Query(20, ge=1, le=100),
    province: Optional[str] = Query(None),
):
    filter_clauses = []
    if province:
        filter_clauses.append({"term": {"province": province}})

    body = {
        "size": 0,
        "query": {"bool": {"filter": filter_clauses}} if filter_clauses else {"match_all": {}},
        "aggs": {
            "top_breeds": {
                "terms": {"field": "breed.keyword", "size": limit, "order": {"_count": "desc"}},
                "aggs": {
                    "avg_price": {"avg": {"field": "price"}},
                    "units": {"terms": {"field": "unit", "size": 1}}
                }
            }
        }
    }
    try:
        result = es.search(index=ES_INDEX, body=body)
        buckets = result["aggregations"]["top_breeds"]["buckets"]
        return {
            "data": [
                {
                    "breed": b["key"],
                    "count": b["doc_count"],
                    "avg_price": round(b["avg_price"]["value"], 2) if b["avg_price"]["value"] else 0,
                    "unit": b["units"]["buckets"][0]["key"] if b["units"]["buckets"] else ""
                }
                for b in buckets
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/filter-options")
def filter_options():
    try:
        # Province + city in one query using composite agg
        province_city_agg = es.search(index=ES_INDEX, size=0, aggs={
            "by_province": {
                "terms": {"field": "province", "size": 50, "order": {"_count": "desc"}},
                "aggs": {
                    "cities": {
                        "terms": {"field": "city", "size": 100},
                        "aggs": {
                            "counties": {
                                "terms": {"field": "county", "size": 100}
                            }
                        }
                    }
                }
            }
        })
        # Build flat city + county lists with parent linkage
        city_list = []
        county_list = []
        province_city_map = {}  # province -> [{key, count}]

        for pb in province_city_agg["aggregations"]["by_province"]["buckets"]:
            prov = pb["key"]
            province_city_map[prov] = []
            for cb in pb["cities"]["buckets"]:
                city_key = cb["key"]
                if city_key:
                    city_list.append({"key": city_key, "count": cb["doc_count"], "province": prov})
                    province_city_map[prov].append({"key": city_key, "count": cb["doc_count"]})
                for tb in cb["counties"]["buckets"]:
                    county_key = tb["key"]
                    if county_key:
                        county_list.append({"key": county_key, "count": tb["doc_count"], "province": prov, "city": city_key})

        return {
            "cities": city_list,
            "counties": county_list,
            "provinceCityMap": province_city_map,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# P2 Features
# ============================================================

@app.get("/api/stats/price-trend")
def price_trend(
    keyword: Optional[str] = Query(None),
    province: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    unit: Optional[str] = Query(None),
    months: int = Query(12, ge=1, le=36),
):
    must_clauses = []
    filter_clauses = []

    if keyword:
        kw_len = len(keyword)
        if kw_len <= 2:
            must_clauses.append({
                "bool": {
                    "should": [
                        {"term": {"breed.keyword": {"value": keyword, "boost": 15}}},
                        {"match": {"breed": {"query": keyword, "fuzziness": "AUTO", "boost": 5}}},
                        {"match": {"spec": {"query": keyword, "fuzziness": "AUTO", "boost": 3}}},
                    ]
                }
            })
        else:
            must_clauses.append({
                "bool": {
                    "should": [
                        {"match_phrase": {"breed": {"query": keyword, "boost": 20}}},
                        {"match": {"breed": {"query": keyword, "operator": "and", "minimum_should_match": "100%", "boost": 10}}},
                        {"match": {"spec": {"query": keyword, "fuzziness": "AUTO", "boost": 5}}},
                    ]
                }
            })
    if province:
        filter_clauses.append({"term": {"province": province}})
    if city:
        filter_clauses.append({"term": {"city": city}})
    if unit:
        filter_clauses.append({"term": {"unit": unit}})

    query = _build_bool_query(must_clauses, filter_clauses)

    body = {
        "query": query,
        "size": 0,
        "aggs": {
            "price_over_time": {
                "date_histogram": {
                    "field": "date",
                    "calendar_interval": "month",
                    "format": "yyyy-MM",
                    "min_doc_count": 1,
                    "order": {"_key": "asc"}
                },
                "aggs": {
                    "avg_price": {"avg": {"field": "price"}},
                    "max_price": {"max": {"field": "price"}},
                    "min_price": {"min": {"field": "price"}},
                    "count": {"value_count": {"field": "price"}}
                }
            }
        }
    }
    try:
        result = es.search(index=ES_INDEX, body=body)
        buckets = result["aggregations"]["price_over_time"]["buckets"]
        return {
            "data": [
                {
                    "month": b["key_as_string"],
                    "count": b["count"]["value"],
                    "avg_price": round(b["avg_price"]["value"], 2) if b["avg_price"]["value"] else None,
                    "max_price": b["max_price"]["value"] or None,
                    "min_price": b["min_price"]["value"] or None,
                }
                for b in buckets[-months:]
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats/price-distribution")
def price_distribution(
    province: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    unit: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
):
    must_clauses = []
    filter_clauses = []

    if category:
        filter_clauses.append({"term": {"category": category}})

    if keyword:
        kw_len = len(keyword)
        if kw_len <= 2:
            must_clauses.append({
                "bool": {
                    "should": [
                        {"term": {"breed.keyword": {"value": keyword, "boost": 15}}},
                        {"match": {"breed": {"query": keyword, "fuzziness": "AUTO", "boost": 5}}},
                        {"match": {"spec": {"query": keyword, "fuzziness": "AUTO", "boost": 3}}},
                    ]
                }
            })
        else:
            must_clauses.append({
                "bool": {
                    "should": [
                        {"match_phrase": {"breed": {"query": keyword, "boost": 20}}},
                        {"match": {"breed": {"query": keyword, "operator": "and", "minimum_should_match": "100%", "boost": 10}}},
                        {"match": {"spec": {"query": keyword, "fuzziness": "AUTO", "boost": 5}}},
                    ]
                }
            })
    if province:
        filter_clauses.append({"term": {"province": province}})
    if city:
        filter_clauses.append({"term": {"city": city}})
    if unit:
        filter_clauses.append({"term": {"unit": unit}})

    query = _build_bool_query(must_clauses, filter_clauses)

    body = {
        "query": query,
        "size": 0,
        "aggs": {
            "ranges": {
                "range": {
                    "field": "price",
                    "ranges": [
                        {"key": "50-100",     "from": 50,      "to": 100},
                        {"key": "100-200",    "from": 100,     "to": 200},
                        {"key": "200-500",    "from": 200,     "to": 500},
                        {"key": "500-700",    "from": 500,     "to": 700},
                        {"key": "700-1000",   "from": 700,     "to": 1000},
                        {"key": "1000-2000",  "from": 1000,    "to": 2000},
                        {"key": "2000-3000",  "from": 2000,    "to": 3000},
                        {"key": "3000-4000",  "from": 3000,    "to": 4000},
                        {"key": "4000-5000",  "from": 4000,    "to": 5000},
                        {"key": ">5000",      "from": 5000},

                    ]
                },
                "aggs": {
                    "avg_price": {"avg": {"field": "price"}}
                }
            }
        }
    }
    try:
        result = es.search(index=ES_INDEX, body=body)
        buckets = result["aggregations"]["ranges"]["buckets"]
        return {
            "data": [
                {
                    "range": b["key"],
                    "count": b["doc_count"],
                    "avg_price": round(b["avg_price"]["value"], 2) if b["avg_price"]["value"] else 0,
                }
                for b in buckets
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats/categories")
def stats_categories(size: int = Query(100, ge=1, le=500)):
    """返回所有产品类别及数据量"""
    try:
        body = {
            "size": 0,
            "aggs": {
                "categories": {
                    "terms": {"field": "category", "size": size}
                }
            }
        }
        result = es.search(index=ES_INDEX, body=body)
        buckets = result["aggregations"]["categories"]["buckets"]
        return {
            "data": [
                {"key": b["key"], "count": b["doc_count"]}
                for b in buckets
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats/category-detail")
def stats_category_detail(
    category: str = Query(...),
    province_limit: int = Query(20, ge=1, le=50),
    breed_limit: int = Query(20, ge=1, le=100),
):
    """返回指定类别的省份分布、热门品种"""
    try:
        # Province + breed + price stats in one query
        body = {
            "query": {"term": {"category": category}},
            "size": 0,
            "aggs": {
                "avg_price": {"avg": {"field": "price"}},
                "max_price": {"max": {"field": "price"}},
                "provinces": {
                    "terms": {"field": "province", "size": province_limit}
                },
                "breeds": {
                    "terms": {"field": "breed.keyword", "size": breed_limit},
                    "aggs": {
                        "spec": {"terms": {"field": "spec.keyword", "size": 1}},
                        "province": {"terms": {"field": "province", "size": 1}},
                        "avg_price": {"avg": {"field": "price"}}
                    }
                }
            }
        }
        result = es.search(index=ES_INDEX, body=body)
        aggs = result["aggregations"]

        provinces = [
            {"key": b["key"], "count": b["doc_count"]}
            for b in aggs["provinces"]["buckets"]
        ]

        breeds = [
            {
                "key": b["key"],
                "count": b["doc_count"],
                "spec": b["spec"]["buckets"][0]["key"] if b["spec"]["buckets"] else "",
                "province": b["province"]["buckets"][0]["key"] if b["province"]["buckets"] else "",
                "avg_price": round(b["avg_price"]["value"], 2) if b["avg_price"]["value"] else 0,
            }
            for b in aggs["breeds"]["buckets"]
        ]

        return {
            "data": {
                "avg_price": round(aggs["avg_price"]["value"], 2) if aggs["avg_price"]["value"] else 0,
                "max_price": round(aggs["max_price"]["value"], 2) if aggs["max_price"]["value"] else 0,
                "provinces": provinces,
                "breeds": breeds,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats/category-price-ranges")
def category_price_ranges(category: str = Query(...)):
    """返回指定类别的动态价格区间，按分位数分为5段，每段覆盖约20%数据"""
    try:
        # Get percentiles to build equal-frequency ranges
        stats_body = {
            "query": {"term": {"category": category}},
            "size": 0,
            "aggs": {
                "min_price": {"min": {"field": "price"}},
                "max_price": {"max": {"field": "price"}},
                "avg_price": {"avg": {"field": "price"}},
                "price_percentiles": {
                    "percentiles": {
                        "field": "price",
                        "percents": [15, 35, 50, 65, 85]
                    }
                }
            }
        }
        stats_result = es.search(index=ES_INDEX, body=stats_body)
        aggs = stats_result["aggregations"]
        min_p = aggs["min_price"]["value"] or 0
        max_p = aggs["max_price"]["value"] or 0
        avg_p = aggs["avg_price"]["value"] or 0

        if max_p <= 0:
            return {"data": [], "stats": {"min": 0, "max": 0, "avg": 0}}

        vals = aggs["price_percentiles"]["values"]
        def pct(key):
            key_str = str(key)
            key_float = float(key)
            if key_str in vals:
                return float(vals[key_str])
            for k, v in vals.items():
                if abs(float(k) - key_float) < 0.01:
                    return float(v)
            raise KeyError(key)
        t1 = pct(15.0)
        t2 = pct(35.0)
        t3 = pct(50.0)
        t4 = pct(65.0)
        t5 = pct(85.0)

        def round100(v): return float(round(v / 100) * 100)

        r0 = min_p
        r1 = round100(t1)
        r2 = round100(t2)
        r3 = round100(t3)
        r4 = round100(t4)
        r5 = round100(t5)
        r6 = max_p

        # Avoid zero-width or inverted ranges
        if r1 <= r0: r1 = r0 + 100
        if r2 <= r1: r2 = r1 + 100
        if r3 <= r2: r3 = r2 + 100
        if r4 <= r3: r4 = r3 + 100
        if r5 <= r4: r5 = r4 + 100

        def fmt(lo, hi):
            def k_str(v):
                if v >= 10000:
                    return f"{int(v/1000)}k"
                elif v >= 1000:
                    if v % 1000 == 0:
                        return f"{int(v/1000)}k"
                    return str(int(v))
                else:
                    return str(int(v))
            return f"{k_str(lo)}-{k_str(hi)}"

        def fmt_single(v):
            if v >= 10000:
                return f"{int(v/1000)}k"
            elif v >= 1000:
                if v % 1000 == 0:
                    return f"{int(v/1000)}k"
                return str(int(v))
            else:
                return str(int(v))

        ranges_config = [
            {"key": "远低于均价", "from": r0, "to": r1},
            {"key": "低于均价",   "from": r1,  "to": r2},
            {"key": "接近均价",   "from": r2,  "to": r3},
            {"key": "高于均价",   "from": r3,  "to": r4},
            {"key": "远高于均价", "from": r4,  "to": r5 + 1},
        ]

        body = {
            "query": {"term": {"category": category}},
            "size": 0,
            "aggs": {
                "ranges": {
                    "range": {
                        "field": "price",
                        "ranges": ranges_config
                    },
                    "aggs": {
                        "avg_price": {"avg": {"field": "price"}}
                    }
                }
            }
        }
        result = es.search(index=ES_INDEX, body=body)
        buckets = result["aggregations"]["ranges"]["buckets"]

        data = []
        for b in buckets:
            from_val = b["from"]
            to_val = b["to"]
            is_last = (b["key"] == "远高于均价")
            if is_last:
                label = "> " + fmt_single(from_val)
            else:
                label = fmt(from_val, to_val)
            data.append({
                "range": label,
                "desc": b["key"],
                "count": b["doc_count"],
                "avg_price": round(b["avg_price"]["value"], 2) if b["avg_price"]["value"] else 0,
            })

        return {
            "data": data,
            "stats": {
                "min": round(min_p, 2),
                "max": round(max_p, 2),
                "avg": round(avg_p, 2),
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats/price-change")
def price_change(
    keyword: Optional[str] = Query(None),
    province: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    unit: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    """涨跌榜：计算各产品近30天与上月的均价变化"""
    must_clauses = []
    filter_clauses = []

    if keyword:
        kw_len = len(keyword)
        if kw_len <= 2:
            must_clauses.append({
                "bool": {
                    "should": [
                        {"term": {"breed.keyword": {"value": keyword, "boost": 15}}},
                        {"match": {"breed": {"query": keyword, "fuzziness": "AUTO", "boost": 5}}},
                        {"match": {"spec": {"query": keyword, "fuzziness": "AUTO", "boost": 3}}},
                    ]
                }
            })
        else:
            must_clauses.append({
                "bool": {
                    "should": [
                        {"match_phrase": {"breed": {"query": keyword, "boost": 20}}},
                        {"match": {"breed": {"query": keyword, "operator": "and", "minimum_should_match": "100%", "boost": 10}}},
                        {"match": {"spec": {"query": keyword, "fuzziness": "AUTO", "boost": 5}}},
                    ]
                }
            })
    if province:
        filter_clauses.append({"term": {"province": province}})
    if city:
        filter_clauses.append({"term": {"city": city}})
    if unit:
        filter_clauses.append({"term": {"unit": unit}})

    query = _build_bool_query(must_clauses, filter_clauses)

    body = {
        "query": query,
        "size": 0,
        "aggs": {
            "by_breed": {
                "terms": {
                    "field": "breed.keyword",
                    "size": limit * 3,
                    "order": {"_count": "desc"}
                },
                "aggs": {
                    "last_month": {
                        "filter": {
                            "range": {
                                "date": {
                                    "gte": "now-2M/M",
                                    "lt": "now-1M/M"
                                }
                            }
                        },
                        "aggs": {
                            "avg_price": {"avg": {"field": "price"}},
                            "count": {"value_count": {"field": "price"}}
                        }
                    },
                    "prev_month": {
                        "filter": {
                            "range": {
                                "date": {
                                    "gte": "now-3M/M",
                                    "lt": "now-2M/M"
                                }
                            }
                        },
                        "aggs": {
                            "avg_price": {"avg": {"field": "price"}},
                            "count": {"value_count": {"field": "price"}}
                        }
                    }
                }
            }
        }
    }
    try:
        result = es.search(index=ES_INDEX, body=body)
        items = []
        for b in result["aggregations"]["by_breed"]["buckets"]:
            last = b["last_month"]
            prev = b["prev_month"]
            last_avg = last["avg_price"]["value"]
            prev_avg = prev["avg_price"]["value"]
            if not last_avg or not prev_avg:
                continue
            change = ((last_avg - prev_avg) / prev_avg) * 100
            items.append({
                "breed": b["key"],
                "last_avg_price": round(last_avg, 2),
                "prev_avg_price": round(prev_avg, 2),
                "change_pct": round(change, 2),
                "count": last["count"]["value"],
            })
        items.sort(key=lambda x: x["change_pct"], reverse=True)
        return {"data": items[:limit]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5200)


# ============================================================
