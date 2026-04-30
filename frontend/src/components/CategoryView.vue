<template>
  <div class="cat-page">
    <!-- Page header -->
    <div class="cat-header">
      <div class="cat-title">产品类别分析</div>
      <div class="cat-subtitle">共 {{ totalDocs.toLocaleString() }} 条数据，{{ categories.length }} 个产品类别</div>
    </div>

    <!-- Category grid -->
    <div class="cat-grid" v-if="!selectedCategory">
      <div
        v-for="cat in categories"
        :key="cat.key"
        class="cat-card"
        :style="{ '--accent': getCategoryColor(cat.key) }"
        @click="selectCategory(cat)"
      >
        <div class="cat-card-inner">
          <div class="cat-name">{{ cat.key }}</div>
          <div class="cat-count">{{ cat.count.toLocaleString() }}</div>
          <div class="cat-pct">{{ getPercent(cat.count) }}%</div>
          <div class="cat-bar-wrap">
            <div class="cat-bar" :style="{ width: getPercent(cat.count) + '%' }"></div>
          </div>
          <div class="cat-province-preview" v-if="cat.top_provinces && cat.top_provinces.length">
            <span class="province-chip" v-for="p in cat.top_provinces.slice(0,3)" :key="p.key">
              {{ p.key }} {{ p.count }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Category detail view -->
    <div class="cat-detail" v-else>
      <div class="cat-detail-header">
        <button class="btn-back" @click="selectedCategory = null">← 返回类别</button>
        <div class="cat-detail-title">
          <span class="detail-dot" :style="{ background: getCategoryColor(selectedCategory.key) }"></span>
          {{ selectedCategory.key }}
          <span class="detail-count">{{ selectedCategory.count.toLocaleString() }} 条</span>
        </div>
      </div>

      <!-- Stats row -->
      <div class="detail-stats">
        <div class="stat-card">
          <div class="stat-value">{{ selectedCategory.count.toLocaleString() }}</div>
          <div class="stat-label">数据总量</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ selectedCategory.province_count }}</div>
          <div class="stat-label">涉及省份</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ selectedCategory.avg_price ? '¥' + selectedCategory.avg_price.toFixed(0) : '-' }}</div>
          <div class="stat-label">平均价格</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ selectedCategory.max_price ? '¥' + selectedCategory.max_price.toLocaleString() : '-' }}</div>
          <div class="stat-label">最高价格</div>
        </div>
      </div>

      <!-- Province distribution -->
      <div class="detail-section">
        <div class="section-title">省份分布</div>
        <div class="province-bars">
          <div
            v-for="(prov, idx) in selectedCategory.provinces"
            :key="prov.key"
            class="province-bar-row"
          >
            <div class="province-label">
              <span class="province-name">{{ prov.key }}</span>
              <span class="province-count">{{ prov.count.toLocaleString() }}</span>
            </div>
            <div class="province-bar-track">
              <div
                class="province-bar-fill"
                :style="{
                  width: getProvPercent(prov.count) + '%',
                  background: getProvColor(idx)
                }"
              ></div>
            </div>
            <div class="province-pct">{{ getProvPercent(prov.count).toFixed(1) }}%</div>
          </div>
        </div>
      </div>

      <!-- Price range distribution -->
      <div class="detail-section">
        <div class="section-title">价格区间分布</div>
        <div id="catPriceChart" style="width:100%;height:260px;"></div>
      </div>

      <!-- Top breeds -->
      <div class="detail-section">
        <div class="section-title">热门品种 Top 20</div>
        <div class="breed-table">
          <div class="breed-thead">
            <div class="breed-th">排名</div>
            <div class="breed-th">产品名称</div>
            <div class="breed-th">规格型号</div>
            <div class="breed-th">省份</div>
            <div class="breed-th">均价</div>
            <div class="breed-th">数量</div>
          </div>
          <div
            v-for="(breed, idx) in selectedCategory.breeds"
            :key="breed.key"
            class="breed-row"
            :class="{ 'striped': idx % 2 === 1 }"
          >
            <div class="breed-td rank">{{ idx + 1 }}</div>
            <div class="breed-td breed-name" :title="breed.key">{{ breed.key }}</div>
            <div class="breed-td spec">{{ breed.spec || '-' }}</div>
            <div class="breed-td province">{{ breed.province }}</div>
            <div class="breed-td price">{{ breed.avg_price ? '¥' + breed.avg_price.toFixed(0) : '-' }}</div>
            <div class="breed-td count">{{ breed.count.toLocaleString() }}</div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="loading" class="cat-loading">
      <div class="spinner"></div>
      <span>加载中...</span>
    </div>
    <div v-if="error" class="cat-error">{{ error }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import axios from 'axios'
import { markRaw } from 'vue'
import * as echarts from 'echarts'

const API = 'http://localhost:5200/api'
const loading = ref(false)
const error = ref('')
const categories = ref([])
const totalDocs = ref(0)
const selectedCategory = ref(null)
const priceChartIns = ref(null)

const PROVINCE_COLORS = [
  '#4a90d9','#50c5a8','#f5a623','#e85555','#9b59b6',
  '#34495e','#e67e22','#1abc9c','#3498db','#95a5a6',
  '#e74c3c','#2ecc71','#f39c12','#c0392b','#7f8c8d',
  '#8e44ad','#16a085','#d35400','#cf5c2a','#e11d48',
]

function getCategoryColor(name) {
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  const hue = Math.abs(hash % 360)
  return `hsl(${hue}, 55%, 48%)`
}

function getProvColor(idx) {
  return PROVINCE_COLORS[idx % PROVINCE_COLORS.length]
}

function getPercent(count) {
  if (!totalDocs.value) return '0'
  return (count / totalDocs.value * 100).toFixed(1)
}

function getProvPercent(count) {
  if (!selectedCategory.value?.count) return 0
  return count / selectedCategory.value.count * 100
}

async function loadCategories() {
  loading.value = true
  error.value = ''
  try {
    const [catRes, countRes] = await Promise.all([
      axios.get(`${API}/stats/categories`, { params: { size: 100 } }),
      axios.get(`${API}/stats/overview`),
    ])
    categories.value = catRes.data?.data || []
    totalDocs.value = countRes.data?.total_docs || 0

    // Load top provinces for each category
    const provPromises = categories.value.slice(0, 20).map(cat =>
      axios.get(`${API}/stats/category-detail`, { params: { category: cat.key } })
        .then(r => ({ key: cat.key, data: r.data?.data || {} }))
        .catch(() => null)
    )
    const provResults = await Promise.all(provPromises)
    provResults.forEach(result => {
      if (!result) return
      const cat = categories.value.find(c => c.key === result.key)
      if (cat) {
        cat.top_provinces = result.data.provinces?.slice(0, 5) || []
      }
    })
  } catch (e) {
    error.value = '加载失败：' + (e.message || '网络错误')
  } finally {
    loading.value = false
  }
}

async function selectCategory(cat) {
  selectedCategory.value = { ...cat, provinces: [], breeds: [], avg_price: 0, max_price: 0, province_count: 0 }
  loading.value = true
  try {
    const [detailRes, priceRes] = await Promise.all([
      axios.get(`${API}/stats/category-detail`, { params: { category: cat.key } }),
      axios.get(`${API}/stats/category-price-ranges`, { params: { category: cat.key } }),
    ])
    const detail = detailRes.data?.data || {}
    selectedCategory.value.provinces = detail.provinces || []
    selectedCategory.value.breeds = detail.breeds || []
    selectedCategory.value.avg_price = detail.avg_price || 0
    selectedCategory.value.max_price = detail.max_price || 0
    selectedCategory.value.province_count = selectedCategory.value.provinces.length

    await nextTick()
    renderPriceChart(priceRes.data?.data || [], priceRes.data?.stats)
  } catch (e) {
    error.value = '加载详情失败：' + (e.message || '网络错误')
  } finally {
    loading.value = false
  }
}

function renderPriceChart(ranges, stats) {
  const el = document.getElementById('catPriceChart')
  if (!el || !ranges.length) return
  if (priceChartIns.value) { priceChartIns.value.dispose(); priceChartIns.value = null }

  const chart = markRaw(echarts.init(el))
  priceChartIns.value = chart

  const colors = ['#6dd5ed','#4facfe','#6a85f5','#9b59b6','#a78bfa','#f59e0b','#f97316','#ef4444','#e11d48','#06b6d4','#84cc16']

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1a2332',
      borderColor: '#1e3a5f',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      formatter: params => {
        const p = params[0]
        return `<b>${p.name}</b><br/>数量: <b style="color:#3b9eff">${p.value.toLocaleString()}</b>`
      }
    },
    grid: { left: '3%', right: '4%', bottom: '12%', top: '8%', containLabel: true },
    xAxis: {
      type: 'category',
      data: ranges.map(r => r.range),
      axisLabel: { color: '#94a3b8', fontSize: 10, rotate: 30, interval: 0 },
      axisLine: { lineStyle: { color: '#1e3a5f' } },
      axisTick: { show: false }
    },
    yAxis: {
      name: '产品数量',
      nameTextStyle: { color: '#64748b', fontSize: 10 },
      type: 'value',
      axisLabel: { color: '#64748b', fontSize: 10 },
      splitLine: { lineStyle: { color: '#1e3a5f', type: 'dashed' } }
    },
    series: [{
      type: 'bar',
      data: ranges.map((r, i) => ({ value: r.count, itemStyle: { color: colors[i % colors.length] } })),
      barMaxWidth: 50,
      label: {
        show: true, position: 'top',
        color: '#94a3b8', fontSize: 9,
        formatter: p => p.value >= 1000 ? (p.value/1000).toFixed(0)+'k' : p.value
      }
    }],
  }, true)

  window.addEventListener('resize', () => chart.resize())
}

onMounted(() => loadCategories())
</script>

<style scoped>
.cat-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px 20px;
}

.cat-header {
  background: linear-gradient(135deg, #f8faff, #fff);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.03);
}

.cat-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
}

.cat-subtitle {
  font-size: 13px;
  color: var(--text-2);
  margin-top: 4px;
}

.cat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}

.cat-card {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 2px 6px rgba(0,0,0,0.04);
  position: relative;
  overflow: hidden;
}

.cat-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 4px;
  height: 100%;
  background: var(--accent);
}

.cat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0,0,0,0.08);
  border-color: var(--accent);
}

.cat-card-inner {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cat-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.cat-count {
  font-size: 22px;
  font-weight: 700;
  color: var(--accent);
  line-height: 1.2;
}

.cat-pct {
  font-size: 12px;
  color: var(--text-2);
  margin-top: -2px;
}

.cat-bar-wrap {
  height: 4px;
  background: var(--surface-2);
  border-radius: 2px;
  margin-top: 6px;
  overflow: hidden;
}

.cat-bar {
  height: 100%;
  background: var(--accent);
  border-radius: 2px;
  transition: width 0.4s ease;
}

.cat-province-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 8px;
}

.province-chip {
  font-size: 11px;
  padding: 1px 6px;
  background: var(--surface-2);
  color: var(--text-2);
  border-radius: 3px;
}

/* Detail view */
.cat-detail-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
}

.btn-back {
  padding: 6px 16px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text);
  transition: background 0.2s;
}

.btn-back:hover {
  background: var(--border);
}

.cat-detail-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text);
  display: flex;
  align-items: center;
  gap: 8px;
}

.detail-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  display: inline-block;
}

.detail-count {
  font-size: 13px;
  font-weight: 400;
  color: var(--text-2);
}

.detail-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.stat-card {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px;
  text-align: center;
  box-shadow: 0 2px 6px rgba(0,0,0,0.03);
}

.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--primary-dark);
}

.stat-label {
  font-size: 12px;
  color: var(--text-2);
  margin-top: 4px;
}

.detail-section {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 6px rgba(0,0,0,0.03);
  margin-bottom: 16px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 12px;
}

.province-bars {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 300px;
  overflow-y: auto;
}

.province-bar-row {
  display: grid;
  grid-template-columns: 100px 1fr 50px;
  align-items: center;
  gap: 10px;
}

.province-label {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.province-name {
  font-size: 12px;
  color: var(--text);
  font-weight: 500;
}

.province-count {
  font-size: 11px;
  color: var(--text-2);
}

.province-bar-track {
  height: 8px;
  background: var(--surface-2);
  border-radius: 4px;
  overflow: hidden;
}

.province-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s ease;
}

.province-pct {
  font-size: 11px;
  color: var(--text-2);
  text-align: right;
}

.breed-table {
  font-size: 12px;
  border-collapse: collapse;
  width: 100%;
}

.breed-thead {
  display: grid;
  grid-template-columns: 40px 1fr 120px 80px 80px 80px;
  gap: 8px;
  padding: 8px 10px;
  background: var(--surface-2);
  border-radius: 6px;
  margin-bottom: 4px;
}

.breed-th {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-2);
}

.breed-row {
  display: grid;
  grid-template-columns: 40px 1fr 120px 80px 80px 80px;
  gap: 8px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border-light);
  align-items: center;
}

.breed-row.striped {
  background: var(--surface-2);
}

.breed-td {
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.breed-td.rank {
  font-weight: 700;
  color: var(--text-2);
  text-align: center;
}

.breed-td.breed-name {
  font-weight: 500;
  color: var(--primary-dark);
}

.breed-td.spec, .breed-td.province {
  color: var(--text-2);
}

.breed-td.price {
  font-weight: 600;
  color: var(--primary-dark);
}

.breed-td.count {
  color: var(--text-2);
}

.cat-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 40px;
  color: var(--text-2);
  font-size: 14px;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.cat-error {
  padding: 16px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: var(--danger);
  font-size: 13px;
}
</style>
