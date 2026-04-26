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
    size: int = Query(20, ge=1, le=100),
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
    from_idx = (page - 1) * size

    body = {
        "query": query,
        "from": from_idx,
        "size": size,
        "sort": [{"date": {"order": "desc"}}, {"_score": {"order": "desc"}}]
    }

    try:
        result = es.search(index=ES_INDEX, body=body)
        total = result["hits"]["total"]["value"]
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
            }
            for h in result["hits"]["hits"]
        ]
        return {
            "total": total,
            "page": page,
            "size": size,
            "pages": (total + size - 1) // size,
            "data": hits
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats/overview")
def overview():
    body = {
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
        must_clauses.append({"match": {"breed": keyword}})
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
):
    filter_clauses = []
    if province:
        filter_clauses.append({"term": {"province": province}})
    if city:
        filter_clauses.append({"term": {"city": city}})

    body = {
        "query": {"bool": {"filter": filter_clauses}} if filter_clauses else {"match_all": {}},
        "size": 0,
        "aggs": {
            "price_ranges": {
                "range": {
                    "field": "price",
                    "ranges": [
                        {"key": "0-50", "from": 0, "to": 50},
                        {"key": "50-100", "from": 50, "to": 100},
                        {"key": "100-500", "from": 100, "to": 500},
                        {"key": "500-1000", "from": 500, "to": 1000},
                        {"key": "1000-5000", "from": 1000, "to": 5000},
                        {"key": "5000-10000", "from": 5000, "to": 10000},
                        {"key": "10000+", "from": 10000},
                    ]
                }
            }
        }
    }
    try:
        result = es.search(index=ES_INDEX, body=body)
        buckets = result["aggregations"]["price_ranges"]["buckets"]
        return {
            "data": [{"range": b["key"], "count": b["doc_count"]} for b in buckets]
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5200)
