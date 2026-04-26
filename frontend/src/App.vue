<template>
  <div class="dashboard">
    <!-- Header -->
    <header class="header">
      <div class="header-left">
        <div class="header-logo">🏗️</div>
        <div class="header-title">
          <h1>建材价格看板</h1>
          <span class="subtitle">gov_price_index · {{ overview.total_docs.toLocaleString() }} 条</span>
        </div>
      </div>
      <div class="header-right">
        <div class="doc-count">
          <span>数据总量</span>
          <strong>{{ overview.total_docs.toLocaleString() }}</strong>
        </div>
      </div>
    </header>

    <!-- Stats Cards -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-icon">🗺️</div>
        <div class="stat-label">覆盖省份</div>
        <div class="stat-value">{{ overview.total_provinces }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">🏙️</div>
        <div class="stat-label">覆盖城市</div>
        <div class="stat-value">{{ overview.total_cities }}</div>
      </div>
    </div>

    <!-- Charts Row 1: Price Dist + Province TOP -->
    <div class="charts-row halves">
      <div class="chart-card">
        <div class="chart-card-header">
          <div class="chart-card-title"><span class="icon">💰</span> 价格区间分布</div>
          <div class="chart-card-badge">{{ priceDist.length }} 区间</div>
        </div>
        <div id="distChart"></div>
      </div>
      <div class="chart-card">
        <div class="chart-card-header">
          <div class="chart-card-title"><span class="icon">🗺️</span> 省份数据量 TOP10</div>
          <div class="chart-card-badge">TOP 10</div>
        </div>
        <div id="provinceChart"></div>
      </div>
    </div>

    <!-- Search Section -->
    <div class="search-section">
      <div class="search-section-header">
        <div class="search-section-title">
          <span>🔍</span> 价格搜索
        </div>
      </div>

      <div class="search-bar">
        <div class="search-group">
          <label class="search-label">产品名称</label>
          <input class="search-input input-kw" v-model="searchKeyword" placeholder="输入产品名称/关键词..." @keyup.enter="doSearch()" />
        </div>

        <div class="search-group">
          <label class="search-label">省份</label>
          <CustomSelect
            v-model="searchProvince"
            :options="overview.by_province.map(p => ({ key: p.province, count: p.count }))"
            placeholder="全部省份"
            :searchable="true"
            @change="onProvinceChange"
          />
        </div>

        <div class="search-group">
          <label class="search-label">城市</label>
          <CustomSelect
            v-model="searchCity"
            :options="filteredCities.map(c => ({ key: c.key, count: c.count }))"
            :disabled="!searchProvince"
            placeholder="全部城市"
            :searchable="true"
          />
        </div>

        <div class="search-group">
          <label class="search-label">区县</label>
          <CustomSelect
            v-model="searchCounty"
            :options="filteredCounties.map(c => ({ key: c.key, count: c.count }))"
            placeholder="全部区县"
            :searchable="true"
          />
        </div>

        <div class="search-group">
          <label class="search-label">价格区间</label>
          <div class="price-range">
            <input class="search-input input-price" v-model="priceMin" placeholder="最低" type="number" @keyup.enter="doSearch()" />
            <span class="price-sep">~</span>
            <input class="search-input input-price" v-model="priceMax" placeholder="最高" type="number" @keyup.enter="doSearch()" />
          </div>
        </div>

        <div class="search-actions">
          <button class="btn-search" @click="doSearch()">🔍 搜索</button>
          <button class="btn-reset" @click="resetSearch" title="重置">重置</button>
        </div>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="loading-overlay">
        <div class="loading-spinner"></div>
        <div class="loading-text">正在检索...</div>
      </div>

      <!-- Empty -->
      <div v-else-if="!searchResult.data || !searchResult.data.length" class="empty-state">
        <div class="empty-icon">📋</div>
        <div class="empty-title">暂无数据</div>
        <div class="empty-hint">请尝试调整搜索条件或关键词</div>
      </div>

      <!-- Table -->
      <div class="table-wrapper" v-else>
        <table class="result-table">
          <thead>
            <tr>
              <th @click="sortBy('breed')" :class="{ sorted: sortKey === 'breed' }">
                产品名称 <span class="sort-icon">{{ sortKey === 'breed' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>
              </th>
              <th @click="sortBy('spec')" :class="{ sorted: sortKey === 'spec' }">
                规格 <span class="sort-icon">{{ sortKey === 'spec' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>
              </th>
              <th @click="sortBy('province')" :class="{ sorted: sortKey === 'province' }">
                省份 <span class="sort-icon">{{ sortKey === 'province' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>
              </th>
              <th @click="sortBy('city')" :class="{ sorted: sortKey === 'city' }">
                城市 <span class="sort-icon">{{ sortKey === 'city' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>
              </th>
              <th>区县</th>
              <th>单位</th>
              <th @click="sortBy('price')" :class="{ sorted: sortKey === 'price' }">
                价格 <span class="sort-icon">{{ sortKey === 'price' ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>
              </th>
              <th>含税价</th>
              <th>日期</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in sortedData" :key="item.id || JSON.stringify(item)">
              <td :title="item.breed" v-html="highlightKeyword(item.breed)"></td>
              <td :title="item.spec">{{ item.spec || '—' }}</td>
              <td>{{ item.province }}</td>
              <td>{{ item.city }}</td>
              <td>{{ item.county || '—' }}</td>
              <td class="unit-cell">{{ item.unit }}</td>
              <td class="price-cell">{{ fmtCell(item.price) }}</td>
              <td class="tax-price-cell">{{ fmtCell(item.tax_price) }}</td>
              <td class="date-cell">{{ item.date || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div class="pagination" v-if="searchResult.pages && searchResult.pages > 1">
        <button class="page-btn nav" :disabled="searchPage <= 1" @click="prevPage()">‹</button>
        <button
          v-for="p in visiblePages"
          :key="p"
          class="page-btn"
          :class="{ active: p === searchPage }"
          @click="goToPage(p)"
        >{{ p }}</button>
        <button class="page-btn nav" :disabled="searchPage >= searchResult.pages" @click="nextPage()">›</button>
        <div class="page-jump-wrap">
          <span>跳至</span>
          <input class="page-jump" v-model.number="jumpPage" @keyup.enter="goToPage(jumpPage)" type="number" min="1" :max="searchResult.pages" />
          <span>页</span>
        </div>
      </div>
    </div>
  </div>

  <!-- Toast -->
  <div v-if="toast.show" class="toast">{{ toast.msg }}</div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'
import CustomSelect from './components/CustomSelect.vue'

const API = 'http://localhost:5200'

// === State ===
const overview = ref({ total_docs: 0, total_provinces: 0, total_cities: 0, avg_price: 0, max_price: 0, min_price: 0, by_province: [] })
const priceDist = ref([])
const searchKeyword = ref('')
const searchProvince = ref('')
const searchCity = ref('')
const searchCounty = ref('')
const priceMin = ref('')
const priceMax = ref('')
const searchPage = ref(1)
const loading = ref(false)
const searchResult = ref({})
const cityOptions = ref([])
const countyOptions = ref([])
const provinceCityMap = ref({})  // province -> [{key, count}]
const jumpPage = ref(1)

// Sort
const sortKey = ref('')
const sortDir = ref('asc')

// Toast
const toast = ref({ show: false, msg: '' })

// Chart instances
let distChart, provinceChart

// === Computed ===
const filteredCities = computed(() => {
  if (!searchProvince.value) return cityOptions.value
  return provinceCityMap.value[searchProvince.value] || []
})

const filteredCounties = computed(() => {
  if (!searchCity.value) return countyOptions.value
  return countyOptions.value.filter(c => c.city === searchCity.value)
})

const sortedData = computed(() => {
  if (!searchResult.value.data || !sortKey.value) return searchResult.value.data || []
  return [...searchResult.value.data].sort((a, b) => {
    const va = a[sortKey.value] ?? ''
    const vb = b[sortKey.value] ?? ''
    const cmp = typeof va === 'number' ? va - vb : String(va).localeCompare(String(vb))
    return sortDir.value === 'asc' ? cmp : -cmp
  })
})

const visiblePages = computed(() => {
  if (!searchResult.value.pages) return []
  const total = searchResult.value.pages
  const cur = searchPage.value
  const pages = []
  const delta = 2
  for (let i = Math.max(1, cur - delta); i <= Math.min(total, cur + delta); i++) {
    pages.push(i)
  }
  return pages
})

// === Helpers ===
function fmtPrice(v) {
  if (!v && v !== 0) return '0.00'
  if (v >= 10000) return (v / 10000).toFixed(1) + '万'
  return Number(v).toFixed(2)
}

function fmtCell(v) {
  if (v == null || v === '') return '—'
  const n = Number(v)
  return isNaN(n) ? v : '¥' + n.toFixed(2)
}

function highlightKeyword(text) {
  if (!text || !searchKeyword.value) return text
  const kw = searchKeyword.value.trim()
  if (!kw) return text
  const re = new RegExp(`(${kw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
  return String(text).replace(re, '<span class="breed-match">$1</span>')
}

function showToast(msg) {
  toast.value = { show: true, msg }
  setTimeout(() => { toast.value.show = false }, 3000)
}

async function loadAPI(url) {
  return axios.get(`${API}${url}`).then(r => r.data).catch(e => {
    showToast('请求失败: ' + (e.message || '网络错误'))
    return {}
  })
}

function sortBy(key) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'asc'
  }
}

function goToPage(p) {
  if (!p || p < 1 || p > (searchResult.value.pages || 1)) return
  jumpPage.value = p
  searchPage.value = p
  doSearch(p)
}

function nextPage() {
  searchPage.value++
  jumpPage.value = searchPage.value
  doSearch(Number(searchPage.value))
}

function prevPage() {
  searchPage.value--
  jumpPage.value = searchPage.value
  doSearch(Number(searchPage.value))
}

function resetSearch() {
  searchKeyword.value = ''
  searchProvince.value = ''
  searchCity.value = ''
  searchCounty.value = ''
  priceMin.value = ''
  priceMax.value = ''
  searchPage.value = 1
  sortKey.value = ''
  sortDir.value = 'asc'
  searchResult.value = {}
}

// === City/County Cascade ===
function onProvinceChange() {
  searchCity.value = ''
  searchCounty.value = ''
}

// === Data Loading ===
async function loadOverview() {
  const data = await loadAPI('/api/stats/overview')
  overview.value = data
}

async function loadPriceDist() {
  const data = await loadAPI('/api/stats/price-distribution')
  priceDist.value = data.data || []
  await nextTick()
  renderDistChart()
}

async function loadCityOptions() {
  const data = await loadAPI('/api/filter-options')
  cityOptions.value = data.cities || []
  countyOptions.value = data.counties || []
  provinceCityMap.value = data.provinceCityMap || {}
}

async function doSearch(pageOverride) {
  if (!pageOverride) {
    searchPage.value = 1
    jumpPage.value = 1
  }
  loading.value = true
  const params = new URLSearchParams()
  if (searchKeyword.value) params.append('keyword', searchKeyword.value)
  if (searchProvince.value) params.append('province', searchProvince.value)
  if (searchCity.value) params.append('city', searchCity.value)
  if (searchCounty.value) params.append('county', searchCounty.value)
  if (priceMin.value) params.append('price_min', priceMin.value)
  if (priceMax.value) params.append('price_max', priceMax.value)
  params.append('page', searchPage.value)
  params.append('size', 20)
  try {
    const data = await loadAPI('/api/search?' + params.toString())
    searchResult.value = data || {}
  } finally {
    loading.value = false
  }
}

// === Charts ===
function renderDistChart() {
  try {
    const el = document.getElementById('distChart')
    if (!el) return
    if (!distChart) distChart = echarts.init(el)
    const raw = priceDist.value
    if (!raw || !raw.length) return
    const colors = ['#3b9eff','#5cdbd3','#34d399','#fbbf24','#f87171','#a78bfa','#fb923c','#38bdf8','#4ade80','#facc15']
    const data = raw.map((d, i) => ({ name: d.range || '未知', value: d.count, itemStyle: { color: colors[i % colors.length] } }))
    distChart.setOption({
      tooltip: { trigger: 'item', backgroundColor: '#1a2332', borderColor: '#1e3a5f', textStyle: { color: '#e2e8f0', fontSize: 12 }, formatter: p => `<b>${p.name}</b><br/>数量: <b style="color:#5cdbd3">${p.value.toLocaleString()}</b> 条<br/>占比: <b>${p.percent.toFixed(1)}%</b>` },
      legend: { orient: 'horizontal', bottom: 0, textStyle: { color: '#94a3b8', fontSize: 11 }, pageTextStyle: { color: '#94a3b8' } },
      series: [{ type: 'pie', radius: ['38%', '68%'], center: ['50%', '45%'], avoidLabelOverlap: true, itemStyle: { borderColor: '#0f172a', borderWidth: 2 }, label: { show: true, formatter: '{b}\n{d}%', fontSize: 10, color: '#94a3b8' }, emphasis: { scale: true, scaleSize: 6 }, data }]
    }, true)
  } catch(e) { console.warn('renderDistChart error:', e) }
}

function renderProvinceChart() {
  try {
    const el = document.getElementById('provinceChart')
    if (!el) return
    if (!provinceChart) provinceChart = echarts.init(el)
    const top10 = [...(overview.value.by_province || [])].sort((a, b) => b.count - a.count).slice(0, 10)
    provinceChart.setOption({
      tooltip: { trigger: 'axis', backgroundColor: '#1a2332', borderColor: '#1e3a5f', textStyle: { color: '#e2e8f0', fontSize: 12 }, axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(59,158,255,0.05)' } }, formatter: p => `<b>${p[0].name}</b><br/>数据量: <b style="color:#5cdbd3">${p[0].value.toLocaleString()}</b> 条` },
      grid: { left: '3%', right: '4%', bottom: '3%', top: '3%', containLabel: true },
      xAxis: { type: 'value', axisLabel: { color: '#64748b', fontSize: 10 }, splitLine: { lineStyle: { color: '#1e3a5f', type: 'dashed' } } },
      yAxis: { type: 'category', data: top10.map(p => p.province).reverse(), axisLabel: { color: '#94a3b8', fontSize: 11 }, axisLine: { lineStyle: { color: '#1e3a5f' } }, axisTick: { show: false } },
      series: [{
        type: 'bar',
        data: top10.map((p, i) => ({
          value: p.count,
          itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [{ offset: 0, color: '#1e5fa8' }, { offset: 1, color: '#3b9eff' }]), borderRadius: [0, 3, 3, 0] }
        })).reverse(),
        label: { show: true, position: 'right', formatter: p => p.value.toLocaleString(), fontSize: 10, color: '#94a3b8' },
        barMaxWidth: 24
      }]
    }, true)
  } catch(e) { console.warn('renderProvinceChart error:', e) }
}

// === Mount ===
onMounted(async () => {
  await loadOverview()
  await nextTick()
  renderProvinceChart()
  await Promise.all([loadPriceDist(), loadCityOptions()])
  window.addEventListener('resize', () => {
    distChart?.resize()
    provinceChart?.resize()
  })
  // Keyboard shortcut: / to focus search
  document.addEventListener('keydown', e => {
    if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'SELECT') {
      e.preventDefault()
      document.querySelector('.input-kw')?.focus()
    }
  })
})
</script>

