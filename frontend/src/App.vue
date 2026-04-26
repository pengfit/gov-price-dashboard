<template>
  <div class="dashboard">

    <!-- ========== TOP BAR ========== -->
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
        <span class="meta-sep">|</span>
        <span class="meta-item">
          <span class="meta-label">均价</span>
          <span class="meta-value accent">{{ overview.avg_price > 0 ? '¥' + fmtCell(overview.avg_price) : '—' }}</span>
        </span>
        <span class="meta-sep">|</span>
        <span class="meta-item meta-refresh" @click="refreshAll" title="刷新数据">
          <span class="icon">🔄</span>
          <span class="meta-label">刷新</span>
        </span>
      </div>
    </header>

    <!-- ========== MAIN LAYOUT ========== -->
    <div class="main-layout">

      <!-- LEFT: Filter Sidebar -->
      <aside class="filter-sidebar">
        <div class="sidebar-section">
          <div class="sidebar-section-title">🔍 筛选条件</div>

          <!-- Keyword -->
          <div class="filter-group">
            <label class="filter-label">产品名称</label>
            <input
              class="filter-input"
              v-model="searchKeyword"
              placeholder="输入产品名称/关键词..."
              @keyup.enter="doSearch()"
              @input="onKeywordInput"
            />
            <!-- Search history -->
            <div class="search-history" v-if="searchHistory.length && !searchKeyword">
              <div class="history-label">最近搜索</div>
              <span
                v-for="h in searchHistory"
                :key="h"
                class="history-chip"
                @click="searchKeyword = h; doSearch()"
              >{{ h }}</span>
            </div>
          </div>

          <!-- Province -->
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

          <!-- City -->
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

          <!-- County -->
          <div class="filter-group">
            <label class="filter-label">区县</label>
            <CustomSelect
              v-model="searchCounty"
              :options="filteredCounties.map(c => ({ key: c.key, count: c.count }))"
              placeholder="全部区县"
              :searchable="true"
            />
          </div>

          <!-- Price Range -->
          <div class="filter-group">
            <label class="filter-label">价格区间</label>
            <div class="price-range-row">
              <input class="filter-input price-input" v-model="priceMin" placeholder="最低" type="number" @keyup.enter="doSearch()" />
              <span class="price-dash">—</span>
              <input class="filter-input price-input" v-model="priceMax" placeholder="最高" type="number" @keyup.enter="doSearch()" />
            </div>
            <!-- Quick price presets -->
            <div class="price-presets">
              <span
                v-for="preset in pricePresets"
                :key="preset.label"
                class="preset-chip"
                :class="{ active: isPresetActive(preset) }"
                @click="applyPreset(preset)"
              >{{ preset.label }}</span>
            </div>
          </div>

          <!-- Actions -->
          <div class="filter-actions">
            <button class="btn-primary" @click="doSearch()">🔍 搜索</button>
            <button class="btn-ghost" @click="resetSearch">重置</button>
          </div>
        </div>
      </aside>

      <!-- RIGHT: Content Area -->
      <main class="content-area">

        <!-- Toolbar -->
        <div class="toolbar" v-if="searchResult.data && searchResult.data.length">
          <div class="toolbar-left">
            <span class="table-count">
              共 <strong>{{ searchResult.total?.toLocaleString() }}</strong> 条结果
              <span class="toolbar-page">第 {{ searchPage }} / {{ searchResult.pages || 1 }} 页</span>
            </span>
          </div>
          <div class="toolbar-right">
            <!-- Column config -->
            <div class="col-config-wrap" ref="colConfigRef">
              <button class="toolbar-btn" @click="toggleColConfig" title="列配置">
                📋 列
              </button>
              <div class="col-config-dropdown" v-if="showColConfig">
                <div class="col-config-title">显示列</div>
                <label v-for="col in allColumns" :key="col.key" class="col-toggle">
                  <input type="checkbox" v-model="col.visible" />
                  <span>{{ col.label }}</span>
                </label>
              </div>
            </div>
            <!-- Export -->
            <button class="toolbar-btn" @click="exportCurrentPage" title="导出当前页">
              📥 导出
            </button>
          </div>
        </div>

        <!-- ========== TABLE or LOADING or EMPTY ========== -->

        <!-- Skeleton loading (rows inside table wrapper) -->
        <div class="table-card" v-if="loading">
          <div class="skeleton-header">
            <div class="skeleton-col" v-for="col in visibleColumns" :key="col.key" :style="{ width: col.width + 'px' }"></div>
          </div>
          <div class="skeleton-row" v-for="i in 8" :key="i">
            <div class="skeleton-col" v-for="col in visibleColumns" :key="col.key" :style="{ width: col.width + 'px' }"></div>
          </div>
          <div class="skeleton-footer"></div>
        </div>

        <!-- Empty state -->
        <div v-else-if="!searchResult.data || !searchResult.data.length" class="empty-state">
          <div class="empty-icon">🗺️</div>
          <div class="empty-title">暂无数据</div>
          <div class="empty-hint">
            <div>可能原因：</div>
            <div>· 该省份暂无此类产品的价格记录</div>
            <div>· 价格区间筛选范围过窄</div>
            <div>· 数据更新时间晚于最近日期</div>
          </div>
          <div class="empty-actions">
            <button class="btn-ghost" @click="expandRange">扩大价格范围</button>
            <button class="btn-ghost" @click="resetSearch">清除筛选</button>
          </div>
        </div>

        <!-- Data Table -->
        <div class="table-card" v-else>
          <div class="table-scroll">
            <table class="result-table">
              <thead>
                <tr>
                  <th
                    v-for="col in visibleColumns"
                    :key="col.key"
                    :class="{ sorted: sortKey === col.key, sortable: col.sortable }"
                    :style="{ width: col.width ? col.width + 'px' : undefined }"
                    @click="col.sortable && sortBy(col.key)"
                  >
                    {{ col.label }}
                    <span v-if="col.sortable" class="sort-icon">
                      {{ sortKey === col.key ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(item, idx) in sortedData"
                  :key="item.id || idx"
                  class="data-row"
                  :class="{ 'stale-row': isStale(item.date) }"
                >
                  <!-- Province color bar (frozen col) -->
                  <td class="province-bar-cell">
                    <div class="province-bar" :style="{ background: getProvinceColor(item.province) }"></div>
                    <span
                      class="breed-text"
                      :title="item.breed"
                      v-html="highlightKeyword(item.breed)"
                    ></span>
                  </td>

                  <!-- Spec -->
                  <td class="td-spec" :title="item.spec">
                    <span class="spec-text">{{ item.spec || '—' }}</span>
                  </td>

                  <!-- Province -->
                  <td class="td-province">{{ item.province }}</td>

                  <!-- City -->
                  <td class="td-city">{{ item.city }}</td>

                  <!-- County -->
                  <td class="td-county">{{ item.county || '—' }}</td>

                  <!-- Unit -->
                  <td class="unit-cell">{{ item.unit }}</td>

                  <!-- Price (highlighted) -->
                  <td class="price-cell" :class="getPriceClass(item.price)">
                    <span class="price-value">{{ fmtCell(item.price) }}</span>
                    <span v-if="getPriceBadge(item)" class="price-badge" :class="getPriceBadge(item).cls">
                      {{ getPriceBadge(item).text }}
                    </span>
                  </td>

                  <!-- Tax Price -->
                  <td class="tax-price-cell">
                    <span>{{ fmtCell(item.tax_price) }}</span>
                    <span v-if="getTaxDiffBadge(item)" class="tax-badge">
                      {{ getTaxDiffBadge(item) }}
                    </span>
                  </td>

                  <!-- Date -->
                  <td class="date-cell" :class="{ 'stale-date': isStale(item.date) }">
                    {{ item.date || '—' }}
                  </td>
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
              :class="{ active: Number(p) === Number(searchPage) }"
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

// ============================================================
// STATE
// ============================================================
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
const searchHistory = ref(JSON.parse(localStorage.getItem('gov_price_history') || '[]'))

// Sort
const sortKey = ref('')
const sortDir = ref('asc')

// Column config
const showColConfig = ref(false)
const colConfigRef = ref(null)
const allColumns = ref([
  { key: 'breed',    label: '产品名称',  sortable: true,  visible: true, width: 180 },
  { key: 'spec',     label: '规格',      sortable: true,  visible: true, width: 160 },
  { key: 'province', label: '省份',      sortable: true,  visible: true, width: 80  },
  { key: 'city',     label: '城市',      sortable: true,  visible: true, width: 90  },
  { key: 'county',   label: '区县',      sortable: false, visible: true, width: 90  },
  { key: 'unit',     label: '单位',      sortable: false, visible: true, width: 60  },
  { key: 'price',    label: '价格',      sortable: true,  visible: true, width: 110 },
  { key: 'tax_price',label: '含税价',   sortable: false, visible: true, width: 110 },
  { key: 'date',     label: '日期',      sortable: true,  visible: true, width: 95  },
])

// Price presets
const pricePresets = [
  { label: '0-500',    min: '0',    max: '500' },
  { label: '500-2k',   min: '500',  max: '2000' },
  { label: '2k-1万',  min: '2000', max: '10000' },
  { label: '>1万',    min: '10000', max: '' },
]

// Toast
const toast = ref({ show: false, msg: '' })

// Province colors (palette)
const PROVINCE_COLORS = {
  '辽宁': '#4a90d9', '江苏': '#50c5a8', '新疆': '#f5a623', '陕西': '#e85555',
  '江西': '#9b59b6', '黑龙江': '#34495e', '青海': '#e67e22', '山东': '#1abc9c',
  '上海': '#3498db', '吉林': '#95a5a6', '广东': '#e74c3c', '北京': '#2ecc71',
  '海南': '#f39c12', '重庆': '#c0392b', '宁夏': '#7f8c8d', '湖南': '#8e44ad',
  '内蒙古': '#16a085', '河南': '#d35400', '贵州': '#cf5c2a',
}
let _provinceColorIdx = 0
const _provinceColorList = Object.values(PROVINCE_COLORS)

function getProvinceColor(province) {
  if (PROVINCE_COLORS[province]) return PROVINCE_COLORS[province]
  PROVINCE_COLORS[province] = _provinceColorList[_provinceColorIdx % _provinceColorList.length]
  _provinceColorIdx++
  return PROVINCE_COLORS[province]
}

// ============================================================
// COMPUTED
// ============================================================
const visibleColumns = computed(() => allColumns.value.filter(c => c.visible))

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

// ============================================================
// ACTIONS
// ============================================================
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

    // Save search history
    if (searchKeyword.value.trim()) {
      const kw = searchKeyword.value.trim()
      const hist = searchHistory.value.filter(h => h !== kw)
      hist.unshift(kw)
      searchHistory.value = hist.slice(0, 10)
      localStorage.setItem('gov_price_history', JSON.stringify(searchHistory.value))
    }
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

// Price highlight
function getPriceClass(price) {
  const n = Number(price)
  if (isNaN(n) || !overview.value.avg_price) return ''
  if (n > overview.value.avg_price * 1.5) return 'price-high'
  if (n < overview.value.avg_price * 0.5) return 'price-low'
  return ''
}

function getPriceBadge(item) {
  const n = Number(item.price)
  if (isNaN(n) || !overview.value.avg_price) return null
  if (n > overview.value.avg_price * 2) return { text: '异常高', cls: 'badge-danger' }
  if (n > overview.value.avg_price * 1.5) return { text: '偏高', cls: 'badge-warning' }
  if (n < overview.value.avg_price * 0.5) return { text: '异常低', cls: 'badge-blue' }
  return null
}

function getTaxDiffBadge(item) {
  const p = Number(item.price)
  const tp = Number(item.tax_price)
  if (isNaN(p) || isNaN(tp) || p <= 0) return null
  const diff = (tp - p) / p
  if (diff > 0.2) return '含税溢价 ' + (diff * 100).toFixed(0) + '%'
  return null
}

function isStale(dateStr) {
  if (!dateStr) return false
  const d = new Date(dateStr)
  const now = new Date()
  const diff = (now - d) / (1000 * 60 * 60 * 24)
  return diff > 30
}

function onKeywordInput() {}

function isPresetActive(preset) {
  return priceMin.value === preset.min && priceMax.value === preset.max
}

function applyPreset(preset) {
  priceMin.value = preset.min
  priceMax.value = preset.max
  doSearch()
}

function expandRange() {
  priceMin.value = ''
  priceMax.value = ''
}

function toggleColConfig() {
  showColConfig.value = !showColConfig.value
}

function exportCurrentPage() {
  const headers = visibleColumns.value.map(c => c.label).join(',')
  const rows = sortedData.value.map(item =>
    visibleColumns.value.map(c => {
      const val = item[c.key]
      return typeof val === 'string' && val.includes(',') ? `"${val}"` : (val ?? '')
    }).join(',')
  ).join('\n')
  const csv = '\uFEFF' + headers + '\n' + rows
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `建材价格_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

async function refreshAll() {
  await Promise.all([loadOverview(), loadCityOptions()])
  if (searchKeyword.value || searchProvince.value || searchCity.value || searchCounty.value || priceMin.value || priceMax.value) {
    await doSearch()
  }
  showToast('数据已刷新')
}

function showToast(msg) {
  toast.value = { show: true, msg }
  setTimeout(() => { toast.value.show = false }, 3000)
}

// Close column config on outside click
function handleDocClick(e) {
  if (colConfigRef.value && !colConfigRef.value.contains(e.target)) {
    showColConfig.value = false
  }
}

// ============================================================
// API
// ============================================================
async function loadAPI(url) {
  try { return (await axios.get(url)).data } catch { return {} }
}

async function loadOverview() {
  const d = await loadAPI(`${API}/stats/overview`)
  overview.value = d || { total_docs: 0, total_provinces: 0, total_cities: 0, avg_price: 0, by_province: [] }
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

onMounted(() => {
  document.addEventListener('click', handleDocClick)
})

onMounted(onMount)

// Keyboard shortcuts
onMounted(() => {
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      showColConfig.value = false
    }
    if ((e.key === '/' || (e.ctrlKey && e.key === 'k')) && !e.target.matches('input, textarea')) {
      e.preventDefault()
      document.querySelector('.filter-input')?.focus()
    }
  })
})
</script>
