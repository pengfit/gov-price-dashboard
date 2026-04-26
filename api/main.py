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
            "total_docs": {"value_count": {"field": "price"}},
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
        result = es.search(index=ES_INDEX, body=body)
        aggs = result["aggregations"]
        province_buckets = aggs["by_province"]["buckets"]
        return {
            "total_docs": int(aggs["total_docs"]["value"]),
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
        unit_agg = es.search(index=ES_INDEX, size=0, aggs={
            "units": {"terms": {"field": "unit", "size": 50, "order": {"_count": "desc"}}}
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
            "units": [{"key": b["key"], "count": b["doc_count"]} for b in unit_agg["aggregations"]["units"]["buckets"] if b["key"]],
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
            "ranges": {
                "range": {
                    "field": "price",
                    "ranges": [
                        {"key": "0-500",    "from": 0,     "to": 500},
                        {"key": "500-2k",   "from": 500,   "to": 2000},
                        {"key": "2k-5k",    "from": 2000,  "to": 5000},
                        {"key": "5k-1万",   "from": 5000,  "to": 10000},
                        {"key": "1万-5万",  "from": 10000, "to": 50000},
                        {"key": ">5万",     "from": 50000},
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
