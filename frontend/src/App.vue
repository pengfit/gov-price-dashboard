<template>
  <div class="dashboard">
    <!-- Header Bar -->
    <header class="top-bar">
      <div class="top-bar-left">
        <div class="top-bar-logo">🏗️</div>
        <div class="top-bar-title">建材价格看板</div>
      </div>
      <div class="top-bar-meta">
        <span class="meta-item">
          <span class="meta-label">数据总量</span>
          <span class="meta-value">{{ overview.total_docs.toLocaleString() }}</span>
        </span>
        <span class="meta-sep">|</span>
        <span class="meta-item">
          <span class="meta-label">省份</span>
          <span class="meta-value">{{ overview.total_provinces }}</span>
        </span>
        <span class="meta-sep">|</span>
        <span class="meta-item">
          <span class="meta-label">城市</span>
          <span class="meta-value">{{ overview.total_cities }}</span>
        </span>
      </div>
    </header>

    <!-- Main Layout: Sidebar + Content -->
    <div class="main-layout">

      <!-- Left Sidebar: Filters -->
      <aside class="filter-sidebar">
        <div class="sidebar-section">
          <div class="sidebar-section-title">🔍 筛选条件</div>

          <div class="filter-group">
            <label class="filter-label">产品名称</label>
            <input class="filter-input" v-model="searchKeyword" placeholder="输入产品名称/关键词..." @keyup.enter="doSearch()" />
          </div>

          <div class="filter-group">
            <label class="filter-label">省份</label>
            <CustomSelect
              v-model="searchProvince"
              :options="overview.by_province.map(p => ({ key: p.province, count: p.count }))"
              placeholder="全部省份"
              :searchable="true"
              @change="onProvinceChange"
            />
          </div>

          <div class="filter-group">
            <label class="filter-label">城市</label>
            <CustomSelect
              v-model="searchCity"
              :options="filteredCities.map(c => ({ key: c.key, count: c.count }))"
              :disabled="!searchProvince"
              placeholder="全部城市"
              :searchable="true"
            />
          </div>

          <div class="filter-group">
            <label class="filter-label">区县</label>
            <CustomSelect
              v-model="searchCounty"
              :options="filteredCounties.map(c => ({ key: c.key, count: c.count }))"
              placeholder="全部区县"
              :searchable="true"
            />
          </div>

          <div class="filter-group">
            <label class="filter-label">价格区间</label>
            <div class="price-range-row">
              <input class="filter-input price-input" v-model="priceMin" placeholder="最低" type="number" @keyup.enter="doSearch()" />
              <span class="price-dash">—</span>
              <input class="filter-input price-input" v-model="priceMax" placeholder="最高" type="number" @keyup.enter="doSearch()" />
            </div>
          </div>

          <div class="filter-actions">
            <button class="btn-primary" @click="doSearch()">🔍 搜索</button>
            <button class="btn-ghost" @click="resetSearch">重置</button>
          </div>
        </div>
      </aside>

      <!-- Right Content: Results -->
      <main class="content-area">

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
        <div class="table-card" v-else>
          <div class="table-card-header">
            <span class="table-count">共 <strong>{{ searchResult.total?.toLocaleString() }}</strong> 条结果</span>
          </div>
          <div class="table-scroll">
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
      </main>
    </div>
  </div>

  <!-- Toast -->
  <div v-if="toast.show" class="toast">{{ toast.msg }}</div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import axios from 'axios'
import CustomSelect from './components/CustomSelect.vue'

const API = 'http://localhost:5200/api'

// === State ===
const overview = ref({ total_docs: 0, total_provinces: 0, total_cities: 0, avg_price: 0, max_price: 0, min_price: 0, by_province: [] })
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
const provinceCityMap = ref({})
const jumpPage = ref(1)

// Sort
const sortKey = ref('')
const sortDir = ref('asc')

// Toast
const toast = ref({ show: false, msg: '' })

function showToast(msg) {
  toast.value = { show: true, msg }
  setTimeout(() => { toast.value.show = false }, 3000)
}

// === Computed ===
const filteredCities = computed(() => {
  if (!searchProvince.value) return cityOptions.value
  return cityOptions.value.filter(c => c.province === searchProvince.value)
})

const filteredCounties = computed(() => {
  let list = countyOptions.value
  if (searchProvince.value) list = list.filter(c => c.province === searchProvince.value)
  if (searchCity.value) list = list.filter(c => c.city === searchCity.value)
  return list
})

const sortedData = computed(() => {
  const data = searchResult.value.data || []
  if (!sortKey.value) return data
  return [...data].sort((a, b) => {
    let av = a[sortKey.value] ?? ''
    let bv = b[sortKey.value] ?? ''
    av = String(av).toLowerCase()
    bv = String(bv).toLowerCase()
    if (av < bv) return sortDir.value === 'asc' ? -1 : 1
    if (av > bv) return sortDir.value === 'asc' ? 1 : -1
    return 0
  })
})

const visiblePages = computed(() => {
  const total = searchResult.value.pages || 1
  const cur = Number(searchPage.value)
  const range = []
  for (let i = Math.max(1, cur - 2); i <= Math.min(total, cur + 2); i++) range.push(i)
  return range
})

// === Actions ===
function sortBy(key) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'asc'
  }
}

function onProvinceChange() {
  searchCity.value = ''
  searchCounty.value = ''
}

function prevPage() {
  if (searchPage.value <= 1) return
  searchPage.value = String(Number(searchPage.value) - 1)
  doSearch(Number(searchPage.value))
}

function nextPage() {
  if (searchPage.value >= searchResult.value.pages) return
  searchPage.value = String(Number(searchPage.value) + 1)
  doSearch(Number(searchPage.value))
}

function goToPage(p) {
  if (p < 1 || p > (searchResult.value.pages || 1)) return
  searchPage.value = String(p)
  doSearch(Number(searchPage.value))
}

async function doSearch(pageOverride) {
  if (!pageOverride) {
    searchPage.value = '1'
    jumpPage.value = 1
    sortKey.value = ''
    sortDir.value = 'asc'
  }
  loading.value = true
  try {
    const params = {}
    if (searchKeyword.value.trim()) params.keyword = searchKeyword.value.trim()
    if (searchProvince.value) params.province = searchProvince.value
    if (searchCity.value) params.city = searchCity.value
    if (searchCounty.value) params.county = searchCounty.value
    if (priceMin.value) params.price_min = priceMin.value
    if (priceMax.value) params.price_max = priceMax.value
    params.page = pageOverride || Number(searchPage.value)
    params.page_size = 20
    const { data: res } = await axios.get(`${API}/search`, { params })
    searchResult.value = res || {}
  } catch (e) {
    showToast('请求失败：' + (e.message || '网络错误'))
  } finally {
    loading.value = false
  }
}

function resetSearch() {
  searchKeyword.value = ''
  searchProvince.value = ''
  searchCity.value = ''
  searchCounty.value = ''
  priceMin.value = ''
  priceMax.value = ''
  searchPage.value = '1'
  jumpPage.value = 1
  sortKey.value = ''
  sortDir.value = 'asc'
  searchResult.value = {}
}

function highlightKeyword(text) {
  if (!text || !searchKeyword.value.trim()) return text
  const kw = searchKeyword.value.trim()
  const regex = new RegExp(`(${kw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
  return String(text).replace(regex, '<span class="breed-match">$1</span>')
}

function fmtCell(v) {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  if (isNaN(n)) return v
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// === API ===
async function loadAPI(url) {
  try { return (await axios.get(url)).data } catch { return {} }
}

async function loadOverview() {
  const d = await loadAPI(`${API}/stats/overview`)
  overview.value = d || { total_docs: 0, total_provinces: 0, total_cities: 0, by_province: [] }
}

async function loadCityOptions() {
  const d = await loadAPI(`${API}/filter-options`)
  if (d) {
    cityOptions.value = d.cities || []
    countyOptions.value = d.counties || []
    provinceCityMap.value = d.provinceCityMap || {}
  }
}

async function onMount() {
  await Promise.all([loadOverview(), loadCityOptions()])
}

// Life
onMounted(onMount)
</script>
