<template>
  <div class="dist-page">
    <!-- Page header -->
    <div class="dist-header">
      <div class="dist-title">数据分布</div>
      <div class="dist-subtitle">各价格区间的产品数量分布</div>
    </div>

    <!-- Chart cards -->
    <div class="dist-cards">
      <div class="dist-card chart-card wide">
        <div class="card-title">价格区间分布</div>
        <div id="rangeBarChart" style="width:100%;height:280px;"></div>
      </div>
    </div>

    <div class="dist-cards">
      <div class="dist-card chart-card wide" style="min-height:640px;">
        <div class="card-title">各省价格分布</div>
        <div class="province-chart-grid">
          <div
            v-for="p in provinceData"
            :key="p.province"
            class="province-chart-cell"
          >
            <div class="province-chart-title">{{ p.province }}</div>
            <div :id="'provinceChart_' + p.province" class="province-chart-box"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Range table -->
    <div class="dist-card table-card">
      <div class="card-title">价格区间明细</div>
      <table class="dist-table">
        <thead>
          <tr>
            <th>价格区间</th>
            <th>产品数量</th>
            <th>占比</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in rangeData" :key="item.range">
            <td><span class="range-badge">{{ item.range }}</span></td>
            <td>{{ item.count.toLocaleString() }}</td>
            <td>
              <div class="pct-bar-wrap">
                <div class="pct-bar" :style="{ width: getPct(item.count) + '%', background: getRangeColor(item.range) }"></div>
                <span class="pct-label">{{ getPct(item.count) }}%</span>
              </div>
            </td>

          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="loading" class="dist-loading">加载中...</div>
    <div v-if="error" class="dist-error">{{ error }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch, onUnmounted } from 'vue'
import axios from 'axios'
import { markRaw } from 'vue'
import * as echarts from 'echarts'

onUnmounted(() => {
  mountedRef.value = false
  rangeBarIns.value?.dispose()
  
})

const props = defineProps({
  keyword: { type: String, default: '' },
  province: { type: String, default: '' },
  city: { type: String, default: '' },
})

const API = 'http://localhost:5200/api'
const loading = ref(false)
const error = ref('')
const rangeData = ref([])
const provinceData = ref([])
const rangeBarIns = ref(null)
const provinceHeatIns = ref(null)
const mountedRef = ref(true)

watch(() => [props.province, props.city], () => {
  if (mountedRef.value) loadData()
}, { deep: true })

const RANGE_COLORS = ['#6dd5ed','#4facfe','#6a85f5','#9b59b6','#a78bfa','#f59e0b','#f97316','#ef4444','#e11d48','#06b6d4']

const PROVINCE_COLORS = {
  '辽宁': '#4a90d9', '江苏': '#50c5a8', '新疆': '#f5a623', '陕西': '#e85555',
  '江西': '#9b59b6', '黑龙江': '#34495e', '青海': '#e67e22', '山东': '#1abc9c',
  '上海': '#3498db', '吉林': '#95a5a6', '广东': '#e74c3c', '北京': '#2ecc71',
  '海南': '#f39c12', '重庆': '#c0392b', '宁夏': '#7f8c8d', '湖南': '#8e44ad',
  '内蒙古': '#16a085', '河南': '#d35400', '贵州': '#cf5c2a',
}
let _pIdx = 0
const _pList = Object.values(PROVINCE_COLORS)
function getProvinceColor(p) {
  if (PROVINCE_COLORS[p]) return PROVINCE_COLORS[p]
  PROVINCE_COLORS[p] = _pList[_pIdx % _pList.length]
  _pIdx++
  return PROVINCE_COLORS[p]
}

function getRangeColor(range) {
  const idx = rangeData.value.findIndex(r => r.range === range)
  return idx >= 0 ? RANGE_COLORS[idx] : '#94a3b8'
}

const totalCount = ref(0)
function getPct(count) {
  if (!totalCount.value) return 0
  return ((count / totalCount.value) * 100).toFixed(1)
}

function getRangePct(count, total) {
  if (!total) return 0
  return (count / total) * 100
}

async function loadData() {
  loading.value = true
  error.value = ''
  try {
    const [distRes, provRes] = await Promise.all([
      axios.get(`${API}/stats/price-distribution`),
      axios.get(`${API}/stats/overview`),
    ])

    rangeData.value = distRes.data?.data || []
    totalCount.value = rangeData.value.reduce((s, r) => s + r.count, 0) || 0

    const overview = provRes.data
    provinceData.value = (overview.by_province || [])
      .sort((a, b) => b.count - a.count)
      .slice(0, 20)
      .map(p => ({
        province: p.province,
        count: p.count,
        avg_price: p.avg_price,
        ranges: []
      }))

    // Load range breakdown per province (always, independent of product-list filters)
    const provNames = provinceData.value.map(p => p.province)
    const rangeBreakdown = await Promise.all(
      provNames.map(prov =>
        axios.get(`${API}/stats/price-distribution`, {
          params: { province: prov }
        }).then(r => ({ prov, ranges: r.data?.data || [] }))
        .catch(() => ({ prov, ranges: [] }))
      )
    )
    const rangeMap = {}
    rangeBreakdown.forEach(({ prov, ranges }) => {
      rangeMap[prov] = ranges
    })
    provinceData.value.forEach(p => {
      p.ranges = rangeMap[p.province] || []
    })

    await nextTick()
    await new Promise(r => setTimeout(r, 50))
    renderRangeBar()
    renderProvinceCharts()
  } catch (e) {
    error.value = '加载失败：' + (e.message || '网络错误')
  } finally {
    loading.value = false
  }
}

function renderRangeBar() {
  const el = document.getElementById('rangeBarChart')
  if (!el || !rangeData.value.length) return
  if (rangeBarIns.value) { rangeBarIns.value.dispose(); rangeBarIns.value = null }
  const chart = markRaw(echarts.init(el))
  rangeBarIns.value = chart

  const sorted = [...rangeData.value]
  const labels = sorted.map(r => r.range)
  const counts = sorted.map(r => r.count)
  const colors = sorted.map(r => getRangeColor(r.range))

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1a2332',
      borderColor: '#1e3a5f',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      formatter: params => {
        const p = params[0]
        return `<b>${p.name}</b><br/>数量: <b style="color:#3b9eff">${p.value.toLocaleString()}</b> 条<br/>占比: <b>${getPct(p.value)}%</b>`
      }
    },
    grid: { left: '3%', right: '4%', bottom: '12%', top: '8%', containLabel: true },
    xAxis: {
      type: 'category', data: labels,
      axisLabel: { color: '#94a3b8', fontSize: 10, rotate: 40, interval: 0 },
      axisLine: { lineStyle: { color: '#1e3a5f' } },
      axisTick: { show: false }
    },
    yAxis: {
      name: '产品数量', nameTextStyle: { color: '#64748b', fontSize: 10 },
      type: 'value',
      axisLabel: { color: '#64748b', fontSize: 10 },
      splitLine: { lineStyle: { color: '#1e3a5f', type: 'dashed' } }
    },
    series: [{
      type: 'bar', data: counts, colorBy: 'data',
      itemStyle: { color: (p) => colors[p.dataIndex] },
      barMaxWidth: 50,
      label: {
        show: true, position: 'top',
        color: '#94a3b8', fontSize: 10,
        formatter: p => p.value >= 1000 ? (p.value/1000).toFixed(0)+'k' : p.value
      }
    }],
  }, true)
  window.addEventListener('resize', () => {
    rangeBarIns.value?.resize()
    provinceHeatIns.value?.resize()
  })
}

function renderProvinceCharts() {
  provinceData.value.forEach((p) => {
    const el = document.getElementById('provinceChart_' + p.province)
    if (!el) return
    const chart = markRaw(echarts.init(el))
    const validRanges = p.ranges.filter(r => r.count)
    if (!validRanges.length) return

    const labels = validRanges.map(r => r.range)
    const values = validRanges.map(r => r.count)
    const colors = validRanges.map(r => {
      const idx = rangeData.value.findIndex(rng => rng.range === r.range)
      return RANGE_COLORS[idx] || '#94a3b8'
    })

    chart.setOption({
      backgroundColor: 'transparent',
      grid: { left: '4%', right: '4%', bottom: '18%', top: '10%', containLabel: true },
      tooltip: {
        backgroundColor: '#1a2332', borderColor: '#1e3a5f',
        textStyle: { color: '#e2e8f0', fontSize: 10 },
        formatter: p => `<b>${p.name}</b><br/>数量: <b style="color:#3b9eff">${p.value.toLocaleString()}</b>`
      },
      xAxis: {
        type: 'category',
        data: labels,
        axisLabel: { color: '#94a3b8', fontSize: 8, rotate: 30, interval: 0 },
        axisLine: { lineStyle: { color: '#1e3a5f' } },
        axisTick: { show: false },
      },
      yAxis: {
        type: 'value', show: false,
        splitLine: { show: false }
      },
      series: [{
        type: 'bar',
        data: values,
        colorBy: 'data',
        itemStyle: { color: (p) => colors[p.dataIndex], borderRadius: [2, 2, 0, 0] },
        barMaxWidth: 28,
        label: {
          show: true, position: 'top',
          color: '#94a3b8', fontSize: 8,
          formatter: p => p.value >= 1000 ? (p.value/1000).toFixed(0)+'k' : p.value
        }
      }],
    })
    setTimeout(() => chart.resize(), 60)
  })
}

onMounted(() => { mountedRef.value = true; loadData() })
</script>

<style scoped>
.dist-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.dist-header {
  padding: 16px 20px;
  background: linear-gradient(135deg, #ffffff, #f7faff);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.03);
}

.dist-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text);
}

.dist-subtitle {
  font-size: 13px;
  color: var(--text-2);
  margin-top: 4px;
}

.dist-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.dist-card {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.03);
}

.dist-card.wide {
  grid-column: 1 / -1;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 12px;
}

.dist-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.dist-table th {
  text-align: left;
  padding: 8px 12px;
  background: var(--surface-2);
  color: var(--text-2);
  font-weight: 500;
  font-size: 12px;
  border-bottom: 1px solid var(--border);
}

.dist-table td {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-light);
  color: var(--text);
}

.dist-table tr:last-child td {
  border-bottom: none;
}

.range-badge {
  display: inline-block;
  padding: 2px 8px;
  background: var(--primary-dim);
  color: var(--primary-dark);
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.province-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}

.pct-bar-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pct-bar {
  height: 6px;
  border-radius: 3px;
  min-width: 4px;
  transition: width 0.3s;
}

.pct-label {
  font-size: 12px;
  color: var(--text-2);
  white-space: nowrap;
}

.mini-bars {
  display: flex;
  height: 14px;
  border-radius: 3px;
  overflow: hidden;
  gap: 1px;
}

.mini-bar-seg {
  height: 100%;
  min-width: 2px;
  transition: width 0.3s;
}

.province-chart-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.province-chart-cell {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.province-chart-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--text);
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.province-chart-box {
  width: 100%;
  height: 160px;
}

.dist-loading, .dist-error {
  text-align: center;
  padding: 24px;
  color: var(--text-2);
  font-size: 13px;
}

.dist-error {
  color: var(--danger);
}
</style>
