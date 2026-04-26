<template>
  <div class="dashboard">

    <!-- ========== TOP BAR ========== -->
    <header class="top-bar">
      <div class="top-bar-left"></div>
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

          <!-- 模式一：顶部快速筛选 -->
          <div class="filter-group">
            <label class="filter-label">产品名称</label>
            <input
              class="filter-input"
              v-model="searchKeyword"
              placeholder="🔍 产品名称 / 关键词"
              @keyup.enter="doSearch()"
              @input="onKeywordInput"
            />
          </div>
          <!-- 省份 -->
          <div class="filter-group">
            <label class="filter-label">省份</label>
            <CustomSelect
              v-model="searchProvince"
              :options="overview.by_province.map(p => ({ key: p.province, count: p.count }))"
              placeholder="全部省份"
              @change="() => { onProvinceChange(); doSearch(); }"
            />
          </div>

          <!-- 最近搜索 -->
          <div class="filter-group">
            <label class="filter-label">最近搜索</label>
            <div class="search-history" v-if="searchHistory.length && !searchKeyword">
              <span
                v-for="h in searchHistory"
                :key="h"
                class="history-chip"
                @click="searchKeyword = h; doSearch()"
              >{{ h }}</span>
            </div>
          </div>

          <!-- 模式二：高级筛选折叠区 -->
          <div class="advanced-filter-toggle" @click="showAdvanced = !showAdvanced">
            <span>🛠️ 高级筛选</span>
            <span class="toggle-arrow" :class="{ open: showAdvanced }">▼</span>
          </div>

          <!-- Advanced filters (collapsible) -->
          <div class="advanced-filters" v-show="showAdvanced">
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
              <strong>{{ pageStart }}‑{{ pageEnd }}</strong>
              / {{ searchResult.total?.toLocaleString() }} 条
            </span>
          </div>
          <div class="toolbar-right">
            <!-- View toggle -->
            <div class="view-tabs">
              <button class="view-tab" :class="{ active: !showChartView }" @click="showChartView = false">📋 列表</button>
              <button class="view-tab" :class="{ active: showChartView }" @click="showChartView = true; loadChartData(true)">📈 图表</button>
            </div>
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

        <!-- ========== TABLE or CHART or LOADING or EMPTY ========== -->
        <Transition name="content-fade">
        <!-- Skeleton loading (rows inside table wrapper) -->
        <div class="content-card" v-if="loading">
          <div class="skeleton-header">
            <div class="skeleton-col" v-for="col in visibleColumns" :key="col.key" :style="{ width: col.width + 'px' }"></div>
          </div>
          <div class="skeleton-row" v-for="i in 8" :key="i">
            <div class="skeleton-col" v-for="col in visibleColumns" :key="col.key" :style="{ width: col.width + 'px' }"></div>
          </div>
          <div class="skeleton-footer"></div>
        </div>

        <!-- Empty state -->
        <div v-else-if="!showChartView && (!searchResult.data || !searchResult.data.length)" class="empty-state">
          <div class="empty-icon">🗺️</div>
          <div class="empty-title">暂无数据</div>
          <div class="empty-hint">
            <div>可能原因：</div>
            <div>· 该省份暂无此类产品的价格记录</div>
            <div>· 数据更新时间晚于最近日期</div>
          </div>
        </div>

        <!-- Data Table -->
        <div class="content-card" v-else-if="!showChartView">
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
                  <td
                    v-for="col in visibleColumns"
                    :key="col.key"
                    :class="getCellClass(col.key, item)"
                    :title="col.key === 'breed' ? item.breed : col.key === 'spec' ? item.spec : undefined"
                  >
                    <template v-if="col.key === 'breed'">
                      <div class="breed-cell">
                        <span class="breed-name" v-html="highlightKeyword(item.breed)"></span>
                        <div class="breed-meta">
                          <span class="meta-tag">{{ item.spec || '—' }}</span>
                          <span class="meta-sep">·</span>
                          <span class="meta-tag">{{ item.city || '—' }}</span>
                        </div>
                      </div>
                    </template>
                    <template v-else-if="col.key === 'spec'"></template>
                    <template v-else-if="col.key === 'province'"></template>
                    <template v-else-if="col.key === 'city'"></template>
                    <template v-else-if="col.key === 'county'"></template>
                    <template v-else-if="col.key === 'unit'">{{ item.unit }}</template>
                    <template v-else-if="col.key === 'price'">
                      <div class="price-main">{{ fmtCell(item.price) }}</div>
                      <div v-if="getPriceChange(item)" class="price-change" :class="getPriceChange(item).cls">{{ getPriceChange(item).text }}</div>
                    </template>
                    <template v-else-if="col.key === 'tax_price'">
                      <div class="price-tax"> {{ fmtCell(item.tax_price) }}</div>
                    </template>
                    <template v-else-if="col.key === 'date'">
                      <span :class="{ 'stale-date': isStale(item.date) }">{{ item.date || '—' }}</span>
                    </template>
                    <template v-else>{{ item[col.key] ?? '—' }}</template>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Pagination -->
          <div class="pagination" v-if="searchResult.pages && searchResult.pages > 1">
            <button class="page-btn nav" :disabled="searchPage <= 1" @click="prevPage()">‹</button>
            <button
              v-for="p in pageRange"
              :key="p"
              class="page-btn"
              :class="{ active: Number(p) === Number(searchPage), ellipsis: p === '...' }"
              :disabled="p === '...'"
              @click="p !== '...' && goToPage(Number(p))"
            >{{ p }}</button>
            <button class="page-btn nav" :disabled="searchPage >= searchResult.pages" @click="nextPage()">›</button>
            <div class="page-jump-wrap">
              <span>跳至</span>
              <input class="page-jump" v-model.number="jumpPage" @keyup.enter="goToPage(jumpPage)" type="number" min="1" :max="searchResult.pages" />
              <span>页</span>
            </div>
            <div class="page-size-wrap">
              <span>每页</span>
              <select class="page-size-select" v-model.number="pageSize" @change="onPageSizeChange">
                <option v-for="s in pageSizeOptions" :key="s" :value="s">{{ s }}</option>
              </select>
              <span>条</span>
            </div>
          </div>
        </div>

        <!-- ========== Chart View (shares same area as table) ========== -->
        <div v-else class="content-card chart-view">
          <div class="change-boards" v-if="changeData.length">
            <div class="change-board gainers">
              <div class="change-board-title">📈 涨幅榜</div>
              <div class="change-item" v-for="item in topGainers" :key="item.breed">
                <span class="change-breed">{{ item.breed }}</span>
                <span class="change-pct up">+{{ item.change_pct }}%</span>
              </div>
            </div>
            <div class="change-board losers">
              <div class="change-board-title">📉 跌幅榜</div>
              <div class="change-item" v-for="item in topLosers" :key="item.breed">
                <span class="change-breed">{{ item.breed }}</span>
                <span class="change-pct down">{{ item.change_pct }}%</span>
              </div>
            </div>
          </div>
          <div class="change-boards-caption">涨幅/跌幅榜 = 近两期（本月 vs 上月）均价变化率，红色数字为品种价格波动幅度排名</div>
        </div>
        </Transition>
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
const pageSize = ref(20)
const pageSizeOptions = [20, 50, 100]
const searchHistory = ref(JSON.parse(localStorage.getItem('gov_price_history') || '[]'))

// Sort
const sortKey = ref('')
const sortDir = ref('asc')

// Column config
const showColConfig = ref(false)
const colConfigRef = ref(null)
const allColumns = ref([
  { key: 'breed',    label: '产品名称',  sortable: true,  visible: true, width: 180 },
  { key: 'price',    label: '价格',      sortable: true,  visible: true, width: 110 },
  { key: 'tax_price',label: '含税价',   sortable: false, visible: true, width: 110 },
  { key: 'unit',     label: '单位',      sortable: false, visible: true, width: 60  },
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

function onPageSizeChange() {
  searchPage.value = '1'
  jumpPage.value = 1
  doSearch(1)
}

const pageStart = computed(() => {
  const s = (Number(searchPage.value) - 1) * pageSize.value + 1
  return s > 0 ? s.toLocaleString() : '0'
})

const pageEnd = computed(() => {
  const e = Math.min(Number(searchPage.value) * pageSize.value, searchResult.value.total || 0)
  return e.toLocaleString()
})

const pageRange = computed(() => {
  const total = searchResult.value.pages || 1
  const cur = Number(searchPage.value)
  if (total <= 7) {
    return Array.from({length: total}, (_, i) => i + 1)
  }
  const range = []
  if (cur <= 4) {
    for (let i = 1; i <= 5; i++) range.push(i)
    range.push('...')
    range.push(total)
  } else if (cur >= total - 3) {
    range.push(1)
    range.push('...')
    for (let i = total - 4; i <= total; i++) range.push(i)
  } else {
    range.push(1)
    range.push('...')
    for (let i = cur - 1; i <= cur + 1; i++) range.push(i)
    range.push('...')
    range.push(total)
  }
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
    params.page_size = pageSize.value

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
function getPriceClass(price, avgPrice) {
  const n = Number(price)
  if (isNaN(n) || !avgPrice) return ''
  if (n > avgPrice * 1.5) return 'price-high'
  if (n < avgPrice * 0.5) return 'price-low'
  return ''
}

function getPriceBadge(item) {
  const n = Number(item.price)
  const av = Number(item.avg_price)
  if (isNaN(n) || !av) return null
  if (n > av * 2) return { text: '异常高', cls: 'badge-danger' }
  if (n > av * 1.5) return { text: '偏高', cls: 'badge-warning' }
  if (n < av * 0.5) return { text: '异常低', cls: 'badge-blue' }
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

function getPriceChange(item) {
  const n = Number(item.price)
  const prev = Number(item.prev_price)
  if (isNaN(n) || isNaN(prev) || prev <= 0) return null
  const pct = ((n - prev) / prev) * 100
  const sign = pct >= 0 ? '+' : ''
  const arrow = pct >= 0 ? '↑' : '↓'
  return {
    text: `${sign}${pct.toFixed(1)}%`,
    cls: pct >= 0 ? 'change-up' : 'change-down'
  }
}

function getCellClass(key, item) {
  if (key === 'price') return 'price-cell ' + getPriceClass(item.price, item.avg_price)
  if (key === 'tax_price') return 'tax-price-cell'
  if (key === 'unit') return 'unit-cell'
  if (key === 'date') return 'date-cell'
  if (key === 'spec') return 'td-spec'
  if (key === 'province') return 'td-province'
  if (key === 'city') return 'td-city'
  if (key === 'county') return 'td-county'
  return ''
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

// Reload overview (with current search filters) when filter state changes
watch(
  [searchKeyword, searchProvince, searchCity, priceMin, priceMax],
  async () => {
    if (Object.keys(searchResult.value).length) {
      await loadOverview()
    }
  }
)

// ============================================================
// API
// ============================================================
async function loadAPI(url) {
  try { return (await axios.get(url)).data } catch { return {} }
}

async function loadOverview() {
  // 不传搜索过滤条件，获取总览全量数据
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

// ============================================================
// P2: Chart Data (uses same filter context as search)
// ============================================================
import { markRaw } from 'vue'
import * as echarts from 'echarts'

const showChartView = ref(false)
const showAdvanced = ref(false)
const quickPricePreset = ref('')

const quickPriceOptions = [
  { key: '', count: 0, label: '不限' },
  { key: '0-3000', count: 0, label: '3000以下' },
  { key: '3000-5000', count: 0, label: '3000-5000' },
  { key: '5000-8000', count: 0, label: '5000-8000' },
  { key: '8000-10000', count: 0, label: '8000-10000' },
  { key: '10000+', count: 0, label: '10000以上' },
]

function onQuickPriceChange() {
  const v = quickPricePreset.value
  if (!v) { priceMin.value = ''; priceMax.value = ''; return }
  if (v === '0-3000') { priceMin.value = ''; priceMax.value = '3000'; }
  else if (v === '3000-5000') { priceMin.value = '3000'; priceMax.value = '5000'; }
  else if (v === '5000-8000') { priceMin.value = '5000'; priceMax.value = '8000'; }
  else if (v === '8000-10000') { priceMin.value = '8000'; priceMax.value = '10000'; }
  else if (v === '10000+') { priceMin.value = '10000'; priceMax.value = ''; }
}
const trendData = ref([])

const changeData = ref([])
const trendChartIns = ref(null)

async function loadChartData(force) {
  // force=true means user switched to chart view — always reload
  if (!force && trendData.value.length) return

  try {
    const params = new URLSearchParams()
    if (searchKeyword.value.trim()) params.append('keyword', searchKeyword.value.trim())
    if (searchProvince.value) params.append('province', searchProvince.value)
    if (searchCity.value) params.append('city', searchCity.value)
    if (priceMin.value) params.append('price_min', priceMin.value)
    if (priceMax.value) params.append('price_max', priceMax.value)
    const [trend, change] = await Promise.all([
      loadAPI(`${API}/stats/price-trend?${params}&months=12`),
      loadAPI(`${API}/stats/price-change?${params}&limit=20`),
    ])
    trendData.value = (trend.data || []).slice(-12)
    changeData.value = change.data || []
    await nextTick()
    renderTrendChart()
  } catch (e) {
    console.warn('chart load error:', e)
  }
}

function renderTrendChart() {
  const el = document.getElementById('trendChart')
  if (!el || !trendData.value.length) return
  if (trendChartIns.value) { trendChartIns.value.dispose(); trendChartIns.value = null }
  const chart = markRaw(echarts.init(el))
  trendChartIns.value = chart
  chart.setOption({
    tooltip: { trigger: 'axis', backgroundColor: '#1a2332', borderColor: '#1e3a5f', textStyle: { color: '#e2e8f0', fontSize: 12 }, formatter: p => `<b>${p[0].name}</b><br/>均价: <b style="color:#3b9eff">¥${p[0].value}</b><br/>数量: <b style="color:#34d399">${p[1]?.value?.toLocaleString() || '-'}</b> 条` },
    legend: { data: ['均价', '数量'], bottom: 0, textStyle: { color: '#94a3b8', fontSize: 10 }, icon: 'roundRect' },
    grid: { left: '3%', right: '4%', bottom: '18%', top: '8%', containLabel: true },
    xAxis: { type: 'category', data: trendData.value.map(d => d.month), axisLabel: { color: '#94a3b8', fontSize: 10 }, axisLine: { lineStyle: { color: '#1e3a5f' } }, axisTick: { show: false } },
    yAxis: [
      { name: '均价', nameTextStyle: { color: '#64748b', fontSize: 9 }, type: 'value', axisLabel: { color: '#64748b', fontSize: 9, formatter: v => v >= 1000 ? (v/1000).toFixed(0)+'k' : v }, splitLine: { lineStyle: { color: '#1e3a5f', type: 'dashed' } } },
      { name: '数量', nameTextStyle: { color: '#64748b', fontSize: 9 }, type: 'value', axisLabel: { color: '#64748b', fontSize: 9 }, splitLine: { show: false } }
    ],
    series: [
      { name: '均价', type: 'line', data: trendData.value.map(d => d.avg_price), smooth: 0.4, color: '#3b9eff', symbol: 'circle', symbolSize: 5, lineStyle: { width: 2 }, areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(59,158,255,0.25)' }, { offset: 1, color: 'rgba(59,158,255,0)' }]) } },
      { name: '数量', type: 'bar', data: trendData.value.map(d => d.count), color: 'rgba(52,211,153,0.6)', yAxisIndex: 1, barMaxWidth: 14 }
    ]
  }, true)
  window.addEventListener('resize', () => trendChartIns.value?.resize())
}


const topGainers = computed(() => (changeData.value || []).filter(x => x.change_pct > 0).slice(0, 10))
const topLosers = computed(() => (changeData.value || []).filter(x => x.change_pct < 0).sort((a, b) => a.change_pct - b.change_pct).slice(0, 10))
</script>
