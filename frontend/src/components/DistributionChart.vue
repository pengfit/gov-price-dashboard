<template>
  <div class="dist-page">
    <!-- Page header -->
    <div class="dist-header">
      <div class="dist-title">数据分布</div>
      <div class="dist-subtitle">各价格区间的产品数量分布</div>
    </div>

    <!-- Chart cards -->
    <div class="dist-cards">
      <div class="dist-card chart-card">
        <div class="card-title">价格区间分布</div>
        <div id="rangeBarChart" style="width:100%;height:280px;"></div>
      </div>

      <div class="dist-card chart-card">
        <div class="card-title">价格占比（饼图）</div>
        <div id="rangePieChart" style="width:100%;height:280px;"></div>
      </div>
    </div>

    <div class="dist-cards">
      <div class="dist-card chart-card wide">
        <div class="card-title">省份-价格热力图</div>
        <div id="provinceHeatChart" style="width:100%;height:300px;"></div>
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
            <th>区间均价</th>
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
            <td>¥{{ item.avg_price?.toLocaleString() || '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Province distribution -->
    <div class="dist-card table-card">
      <div class="card-title">省份产品分布 Top 20</div>
      <table class="dist-table">
        <thead>
          <tr>
            <th>省份</th>
            <th>产品数量</th>
            <th>均价</th>
            <th>价格分布</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in provinceData" :key="item.province">
            <td>
              <span class="province-dot" :style="{ background: getProvinceColor(item.province) }"></span>
              {{ item.province }}
            </td>
            <td>{{ item.count.toLocaleString() }}</td>
            <td>¥{{ item.avg_price?.toLocaleString() || '—' }}</td>
            <td>
              <div class="mini-bars">
                <div
                  v-for="r in item.ranges"
                  :key="r.range"
                  class="mini-bar-seg"
                  :style="{ width: getRangePct(r.count, item.count) + '%', background: getRangeColor(r.range) }"
                  :title="`${r.range}: ${r.count}`"
                ></div>
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
import { ref, onMounted, nextTick } from 'vue'
import axios from 'axios'
import { markRaw } from 'vue'
import * as echarts from 'echarts'

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
const rangePieIns = ref(null)
const provinceHeatIns = ref(null)

const RANGE_COLORS = {
  '0-500':   '#60a5fa',
  '500-2k':  '#34d399',
  '2k-5k':   '#a78bfa',
  '5k-1万':  '#f59e0b',
  '1万-5万': '#f87171',
  '>5万':    '#e879f9',
}

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
  return RANGE_COLORS[range] || '#94a3b8'
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
    const params = {}
    if (props.keyword) params.keyword = props.keyword
    if (props.province) params.province = props.province
    if (props.city) params.city = props.city

    const [distRes, provRes] = await Promise.all([
      axios.get(`${API}/stats/price-distribution`, { params }),
      axios.get(`${API}/stats/overview`, { params }),
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

    // Load range breakdown per province
    if (props.province) {
      // already filtered, no extra call needed
    } else {
      // fetch range breakdown per province via filter-options + price-distribution
      // Use parallel fetch with each province as filter
      const provNames = provinceData.value.map(p => p.province)
      const rangeBreakdown = await Promise.all(
        provNames.map(prov =>
          axios.get(`${API}/stats/price-distribution`, {
            params: { ...params, province: prov }
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
    }

    await nextTick()
    renderRangeBar()
    renderRangePie()
    renderProvinceHeat()
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
      axisLabel: { color: '#94a3b8', fontSize: 11, rotate: 0 },
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
    rangePieIns.value?.resize()
    provinceHeatIns.value?.resize()
  })
}

function renderRangePie() {
  const el = document.getElementById('rangePieChart')
  if (!el || !rangeData.value.length) return
  if (rangePieIns.value) { rangePieIns.value.dispose(); rangePieIns.value = null }
  const chart = markRaw(echarts.init(el))
  rangePieIns.value = chart

  const sorted = [...rangeData.value].filter(r => r.count > 0)
  chart.setOption({
    tooltip: {
      backgroundColor: '#1a2332', borderColor: '#1e3a5f',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      formatter: p => `<b>${p.name}</b><br/>数量: <b>${p.value.toLocaleString()}</b><br/>占比: <b>${p.percent.toFixed(1)}%</b>`
    },
    legend: { bottom: 0, textStyle: { color: '#94a3b8', fontSize: 10 }, itemWidth: 10, itemHeight: 10 },
    series: [{
      type: 'pie', radius: ['35%', '65%'],
      data: sorted.map(r => ({ name: r.range, value: r.count })),
      itemStyle: { borderRadius: 4, borderColor: '#0f172a', borderWidth: 2 },
      label: { color: '#94a3b8', fontSize: 10, formatter: '{b}: {d}%' },
      labelLine: { lineStyle: { color: '#1e3a5f' } },
    }],
  }, true)
}

function renderProvinceHeat() {
  const el = document.getElementById('provinceHeatChart')
  if (!el || !provinceData.value.length) return
  if (provinceHeatIns.value) { provinceHeatIns.value.dispose(); provinceHeatIns.value = null }
  const chart = markRaw(echarts.init(el))
  provinceHeatIns.value = chart

  // Build price-range matrix per province
  const rangeLabels = rangeData.value.map(r => r.range)
  const provinces = provinceData.value.map(p => p.province)

  // Build matrix: for each province, find count per range
  const matrix = provinceData.value.map(p => {
    return rangeLabels.map(r => {
      const found = p.ranges?.find(x => x.range === r)
      return found ? found.count : 0
    })
  })

  // Also compute avg_price per province for tooltip
  const avgPrices = provinceData.value.map(p => p.avg_price)

  chart.setOption({
    tooltip: {
      backgroundColor: '#1a2332', borderColor: '#1e3a5f',
      textStyle: { color: '#e2e8f0', fontSize: 11 },
      formatter: p => {
        const prov = provinces[p.data1]
        const rng = rangeLabels[p.data2]
        const provData = provinceData.value[p.data1]
        return `<b>${prov}</b> / ${rng}<br/>数量: <b style="color:#3b9eff">${p.value}</b><br/>均价: <b>¥${(provData?.avg_price || 0).toLocaleString()}</b>`
      }
    },
    grid: { left: '2%', right: '2%', bottom: '20%', top: '2%', containLabel: true },
    xAxis: { type: 'category', data: rangeLabels, axisLabel: { color: '#94a3b8', fontSize: 10, rotate: 30 }, axisLine: { lineStyle: { color: '#1e3a5f' } }, axisTick: { show: false } },
    yAxis: { type: 'category', data: provinces, axisLabel: { color: '#94a3b8', fontSize: 10 }, axisLine: { lineStyle: { color: '#1e3a5f' } }, axisTick: { show: false } },
    visualMap: {
      min: 0,
      max: Math.max(...matrix.flat(), 1),
      text: ['高', '低'],
      textStyle: { color: '#94a3b8', fontSize: 10 },
      inRange: { color: ['#1a2332', '#1e3a5f', '#3b9eff', '#34d399', '#f59e0b', '#f87171'] },
      calculable: true,
      bottom: 0,
      left: 0,
      itemWidth: 12,
      itemHeight: 100,
    },
    series: [{
      type: 'heatmap',
      data: matrix.flatMap((row, ri) => row.map((v, ci) => [ci, ri, v])),
      label: { show: true, color: '#e2e8f0', fontSize: 9, formatter: p => p.value > 0 ? p.value : '' },
      itemStyle: { borderRadius: 2, borderColor: '#0f172a', borderWidth: 1 },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(59,158,255,0.5)' } }
    }],
  }, true)
}

onMounted(loadData)
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
