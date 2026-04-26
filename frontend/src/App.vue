<template>
  <div class="dashboard">
    <!-- Header -->
    <header class="header">
      <div class="header-left">
        <h1>🏗️ 建材价格看板</h1>
        <span class="subtitle">gov_price_index · 实时数据</span>
      </div>
      <div class="header-right">
        <span class="last-updated">数据总量: <strong>{{ overview.total_docs.toLocaleString() }}</strong> 条</span>
      </div>
    </header>

    <!-- Stats Cards -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-label">覆盖省份</div>
        <div class="stat-value">{{ overview.total_provinces }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">覆盖城市</div>
        <div class="stat-value">{{ overview.total_cities }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">平均价格</div>
        <div class="stat-value">¥{{ overview.avg_price.toLocaleString() }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">最高价格</div>
        <div class="stat-value">¥{{ overview.max_price.toLocaleString() }}</div>
      </div>
    </div>

    <!-- Charts Row -->
    <div class="charts-row">
      <!-- 价格分布 -->
      <div class="chart-card">
        <h3>💰 价格区间分布</h3>
        <div id="distChart" style="height: 280px;"></div>
      </div>
      <!-- 省份文档量 -->
      <div class="chart-card">
        <h3>🗺️ 省份数据量 TOP10</h3>
        <div id="provinceChart" style="height: 280px;"></div>
      </div>
    </div>

    <!-- Search & Products Row -->
    <div class="charts-row">
      <!-- 热门产品 -->
      <div class="chart-card">
        <h3>📊 热门建材 TOP20</h3>
        <div id="topChart" style="height: 320px;"></div>
      </div>
      <!-- 价格走势 -->
      <div class="chart-card">
        <h3>📈 价格走势（近12月）</h3>
        <div class="trend-controls">
          <select v-model="trendProvince" @change="loadTrend">
            <option value="">全国</option>
            <option v-for="p in overview.by_province" :key="p.province" :value="p.province">{{ p.province }}</option>
          </select>
          <input v-model="trendKeyword" placeholder="产品关键词" @keyup.enter="loadTrend" />
          <button @click="loadTrend">搜索</button>
        </div>
        <div id="trendChart" style="height: 250px;"></div>
      </div>
    </div>

    <!-- Search -->
    <div class="search-section">
      <h3>🔍 价格搜索</h3>
      <div class="search-bar">
        <input v-model="searchKeyword" placeholder="输入产品名称/关键词..." @keyup.enter="doSearch()" />
        <select v-model="searchProvince" @change="doSearch()">
          <option value="">全部省份</option>
          <option v-for="p in overview.by_province" :key="p.province" :value="p.province">{{ p.province }}</option>
        </select>
        <select v-model="searchCity">
          <option value="">全部城市</option>
          <option v-for="c in cityOptions" :key="c.key" :value="c.key">{{ c.key }} ({{ c.count }})</option>
        </select>
        <select v-model="searchCounty">
          <option value="">全部区县</option>
          <option v-for="c in countyOptions" :key="c.key" :value="c.key">{{ c.key }} ({{ c.count }})</option>
        </select>
        <input v-model="priceMin" placeholder="最低价" type="number" @keyup.enter="doSearch()" />
        <span>~</span>
        <input v-model="priceMax" placeholder="最高价" type="number" @keyup.enter="doSearch()" />
        <button @click="doSearch()">搜索</button>
        <span class="result-count" v-if="searchResult.total">{{ searchResult.total.toLocaleString() }} 条结果</span>
      </div>

      <!-- Results Table -->
      <table class="result-table" v-if="searchResult.data && searchResult.data.length">
        <thead>
          <tr>
            <th>产品名称</th>
            <th>规格</th>
            <th>省份</th>
            <th>城市</th>
            <th>区县</th>
            <th>单位</th>
            <th>价格</th>
            <th>含税价</th>
            <th>日期</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in searchResult.data" :key="item.id">
            <td>{{ item.breed }}</td>
            <td>{{ item.spec || '-' }}</td>
            <td>{{ item.province }}</td>
            <td>{{ item.city }}</td>
            <td>{{ item.county || '-' }}</td>
            <td>{{ item.unit }}</td>
            <td class="price">{{ item.price ? '¥' + item.price : '-' }}</td>
            <td class="price">{{ item.tax_price ? '¥' + item.tax_price : '-' }}</td>
            <td>{{ item.date || '-' }}</td>
          </tr>
        </tbody>
      </table>

      <!-- Pagination -->
      <div class="pagination" v-if="searchResult.total">
        <button :disabled="searchPage <= 1" @click="prevPage()">上一页</button>
        <span>第 {{ searchPage }} / {{ searchResult.pages || 1 }} 页</span>
        <button :disabled="searchPage >= searchResult.pages" @click="nextPage()">下一页</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'

const API = 'http://localhost:5200'

const overview = ref({ total_docs: 0, total_provinces: 0, total_cities: 0, avg_price: 0, max_price: 0, min_price: 0, by_province: [] })
const priceDist = ref([])
const topProducts = ref([])
const trendData = ref([])

const trendProvince = ref('')
const trendKeyword = ref('')

const searchKeyword = ref('')
const searchProvince = ref('')
const searchCity = ref('')
const searchCounty = ref('')
const priceMin = ref('')
const priceMax = ref('')
const searchPage = ref(1)
const searchResult = ref({})
const cityOptions = ref([])
const countyOptions = ref([])

// 用 id 而非 ref，避免 timing 问题
let distChart, provinceChart, topChart, trendChart

async function loadAPI(url) {
  const resp = await axios.get(`${API}${url}`)
  return resp.data
}

async function loadOverview() {
  overview.value = await loadAPI('/api/stats/overview')
}

async function loadPriceDist() {
  const data = await loadAPI('/api/stats/price-distribution')
  priceDist.value = data.data || []
  await nextTick()
  renderDistChart()
}

async function loadTopProducts() {
  const data = await loadAPI('/api/stats/top-products?limit=20')
  topProducts.value = data.data || []
  await nextTick()
  renderTopChart()
}

async function loadTrend() {
  let url = `/api/stats/price-trend?months=12`
  if (trendProvince.value) url += `&province=${encodeURIComponent(trendProvince.value)}`
  if (trendKeyword.value) url += `&keyword=${encodeURIComponent(trendKeyword.value)}`
  const data = await loadAPI(url)
  trendData.value = data.data || []
  await nextTick()
  renderTrendChart()
}

async function loadCityOptions() {
  const data = await loadAPI('/api/filter-options')
  cityOptions.value = data.cities || []
  countyOptions.value = data.counties || []
}

function nextPage() {
  searchPage.value++
  doSearch(Number(searchPage.value))
}

function prevPage() {
  searchPage.value--
  doSearch(Number(searchPage.value))
}

async function doSearch(pageOverride) {
  searchPage.value = pageOverride || 1
  const params = new URLSearchParams()
  if (searchKeyword.value) params.append('keyword', searchKeyword.value)
  if (searchProvince.value) params.append('province', searchProvince.value)
  if (searchCity.value) params.append('city', searchCity.value)
  if (searchCounty.value) params.append('county', searchCounty.value)
  if (priceMin.value) params.append('price_min', priceMin.value)
  if (priceMax.value) params.append('price_max', priceMax.value)
  params.append('page', searchPage.value)
  params.append('size', 20)
  const data = await loadAPI('/api/search?' + params.toString())
  searchResult.value = data || {}
}

function renderDistChart() {
  const el = document.getElementById('distChart')
  if (!el) { console.warn('distChart element not found'); return }
  if (!distChart) distChart = echarts.init(el)
  const data = priceDist.value.map(d => ({ name: d.range, value: d.count }))
  if (!data.length) { console.warn('priceDist is empty'); return }
  distChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    series: [{
      type: 'pie', radius: ['40%', '70%'], avoidLabelOverlap: true,
      itemStyle: { borderColor: '#fff', borderWidth: 2 },
      label: { show: true, formatter: '{b}\n{c}', fontSize: 10 },
      data, color: ['#36cfc9','#40a9ff','#5cdbd3','#69c0ff','#73d13d','#ffa940','#ff7a45']
    }]
  })
}

function renderProvinceChart() {
  const el = document.getElementById('provinceChart')
  if (!el) return
  if (!provinceChart) provinceChart = echarts.init(el)
  const top10 = [...overview.value.by_province].sort((a,b) => b.count - a.count).slice(0, 10)
  provinceChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '3%', containLabel: true },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: top10.map(p => p.province).reverse(), axisLabel: { fontSize: 11 } },
    series: [{
      type: 'bar',
      data: top10.map(p => p.count).reverse(),
      itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
        { offset: 0, color: '#5cdbd3' },
        { offset: 1, color: '#40a9ff' }
      ]), borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: 'right', formatter: '{c}', fontSize: 10 }
    }]
  })
}

function renderTopChart() {
  const el = document.getElementById('topChart')
  if (!el) { console.warn('topChart element not found'); return }
  if (!topChart) topChart = echarts.init(el)
  const data = topProducts.value
  if (!data.length) { console.warn('topProducts is empty'); return }
  topChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' },
      formatter: p => `${p[0].name}<br/>数量: ${p[0].value?.toLocaleString() || '-'} 条<br/>均价: ¥${(p[0].data?.avg || '-').toLocaleString ? p[0].data.avg.toLocaleString() : p[0].data?.avg || '-'}` },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '3%', containLabel: true },
    xAxis: { type: 'category', data: data.map(p => p.breed).reverse(), axisLabel: { rotate: 30, fontSize: 10, interval: 0 } },
    yAxis: { type: 'value', axisLabel: { fontSize: 10 } },
    series: [{
      type: 'bar',
      data: data.map(p => p.count).reverse(),
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#73d13d' },
          { offset: 1, color: '#95de64' }
        ]), borderRadius: [4, 4, 0, 0]
      },
      label: { show: true, position: 'top', fontSize: 9, formatter: p => p.value.toLocaleString() }
    }]
  })
}

function renderTrendChart() {
  const el = document.getElementById('trendChart')
  if (!el) return
  if (!trendChart) trendChart = echarts.init(el)
  const months = trendData.value.map(d => d.month)
  const avgs = trendData.value.map(d => d.avg_price)
  const counts = trendData.value.map(d => d.count)
  trendChart.setOption({
    tooltip: { trigger: 'axis', formatter: p => `${p[0].name}<br/><span style="color:#40a9ff">均价: ¥${p[0].value || '-'}</span><br/><span style="color:#73d13d">数量: ${p[1]?.value?.toLocaleString() || '-'}</span>` },
    legend: { data: ['均价', '数量'], bottom: 0, textStyle: { fontSize: 10 } },
    grid: { left: '3%', right: '4%', bottom: '18%', top: '5%', containLabel: true },
    xAxis: { type: 'category', data: months, axisLabel: { fontSize: 10 } },
    yAxis: [
      { name: '均价', type: 'value', axisLabel: { fontSize: 9, formatter: v => '¥' + v } },
      { name: '数量', type: 'value', axisLabel: { fontSize: 9 } }
    ],
    series: [
      { name: '均价', type: 'line', data: avgs, smooth: true, color: '#40a9ff', yAxisIndex: 0 },
      { name: '数量', type: 'bar', data: counts, color: '#73d13d', yAxisIndex: 1, opacity: 0.6 }
    ]
  })
}

onMounted(async () => {
  await loadOverview()
  // render province chart after overview loads
  await nextTick()
  renderProvinceChart()
  // load other charts in parallel
  await Promise.all([loadPriceDist(), loadTopProducts(), loadTrend(), loadCityOptions()])
  window.addEventListener('resize', () => {
    distChart?.resize()
    provinceChart?.resize()
    topChart?.resize()
    trendChart?.resize()
  })
})
</script>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
html { font-size: 16px; }
body {
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background: #0f172a;
  color: #e2e8f0;
  text-rendering: optimizeLegibility;
}

.dashboard { max-width: 1600px; margin: 0 auto; padding: 20px; }

.header { display: flex; justify-content: space-between; align-items: center; padding: 16px 24px; background: linear-gradient(135deg, #1e3a5f, #0f2744); border-radius: 12px; margin-bottom: 20px; }
.header h1 { font-size: 24px; color: #fff; }
.subtitle { font-size: 13px; color: #94a3b8; margin-left: 12px; }
.last-updated { font-size: 13px; color: #94a3b8; }
.last-updated strong { color: #5cdbd3; font-size: 18px; }

.stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 20px; }
.stat-card { background: #1e293b; border-radius: 10px; padding: 20px; text-align: center; border: 1px solid #334155; min-width: 0; }
.stat-label { font-size: 12px; color: #94a3b8; margin-bottom: 8px; }
.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #5cdbd3;
  word-break: break-all;
  overflow-wrap: break-word;
  line-height: 1.2;
  letter-spacing: -0.5px;
}

.charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }
.chart-card { background: #1e293b; border-radius: 10px; padding: 20px; border: 1px solid #334155; }
.chart-card h3 { font-size: 15px; color: #e2e8f0; margin-bottom: 16px; font-weight: 500; }

.trend-controls { display: flex; gap: 8px; margin-bottom: 12px; align-items: center; }
.trend-controls select, .trend-controls input { background: #0f172a; border: 1px solid #334155; color: #e2e8f0; border-radius: 6px; padding: 5px 10px; font-size: 13px; }
.trend-controls button { background: #40a9ff; color: #fff; border: none; border-radius: 6px; padding: 5px 14px; cursor: pointer; font-size: 13px; }
.trend-controls input { width: 120px; }

.search-section { background: #1e293b; border-radius: 10px; padding: 20px; border: 1px solid #334155; }
.search-section h3 { font-size: 15px; margin-bottom: 16px; }
.search-bar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 16px; }
.search-bar input { background: #0f172a; border: 1px solid #334155; color: #e2e8f0; border-radius: 6px; padding: 8px 12px; font-size: 13px; }
.search-bar input:first-child { flex: 1; min-width: 200px; }
.search-bar select { background: #0f172a; border: 1px solid #334155; color: #e2e8f0; border-radius: 6px; padding: 8px 10px; font-size: 13px; }
.search-bar button { background: #40a9ff; color: #fff; border: none; border-radius: 6px; padding: 8px 20px; cursor: pointer; font-size: 13px; }
.search-bar span { color: #94a3b8; font-size: 13px; }
.result-count { margin-left: auto; color: #94a3b8; font-size: 13px; }

.result-table { width: 100%; border-collapse: collapse; font-size: 13px; table-layout: fixed; }
.result-table th { background: #0f172a; padding: 10px 8px; text-align: left; color: #94a3b8; border-bottom: 1px solid #334155; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.result-table td { padding: 9px 8px; border-bottom: 1px solid #1e293b; color: #cbd5e1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.result-table td.price { color: #5cdbd3; font-weight: 600; white-space: nowrap; }
.result-table td:nth-child(1) { width: 20%; }
.result-table td:nth-child(2) { width: 18%; }
.result-table td:nth-child(3) { width: 8%; }
.result-table td:nth-child(4) { width: 8%; }
.result-table td:nth-child(5) { width: 8%; }
.result-table td:nth-child(6) { width: 6%; }
.result-table td:nth-child(7) { width: 8%; }
.result-table td:nth-child(8) { width: 8%; }
.result-table td:nth-child(9) { width: 10%; }
.result-table tr:hover td { background: #1e293b; }

.pagination { display: flex; gap: 12px; align-items: center; margin-top: 16px; justify-content: center; }
.pagination button { background: #334155; color: #e2e8f0; border: none; border-radius: 6px; padding: 7px 16px; cursor: pointer; font-size: 13px; }
.pagination button:disabled { opacity: 0.4; cursor: not-allowed; }
.pagination span { font-size: 13px; color: #94a3b8; white-space: nowrap; }
</style>