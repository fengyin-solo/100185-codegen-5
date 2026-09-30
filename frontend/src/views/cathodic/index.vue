<template>
  <section class="page" data-module="cathodic">
    <header class="page-head">
      <div>
        <h2>阴极保护监测台账</h2>
        <p class="page-desc">
          现场保护电位按批次导入，按参比电极与恒电位仪分组逐行校验；同测点重复采集按采集时间覆盖，
          存量记录回填为历史条目，并汇进防腐层检查统计。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="activeTab = 'import'">批次导入</button>
      </div>
    </header>

    <div class="tab-bar">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-item"
        :class="{ active: activeTab === tab.key }"
        type="button"
        @click="switchTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- 恒电位仪总览：最近一次采集结论 + 防腐层检查情况 -->
    <div v-if="activeTab === 'overview'" v-cloak>
      <div class="stat-row">
        <article class="stat-card">
          <span class="stat-label">恒电位仪台数</span>
          <strong class="stat-value">{{ rectifiers.length }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">机组全部达标</span>
          <strong class="stat-value">{{ healthyCount }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">存在异常测点</span>
          <strong class="stat-value">{{ rectifiers.length - healthyCount }}</strong>
        </article>
      </div>
      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in rectifierColumns" :key="column">{{ column }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rectifiers" :key="String(row['恒电位仪编号'])">
            <td v-for="column in rectifierColumns" :key="column">
              <span v-if="column === '机组结论'" :class="row['机组结论'] === '保护达标' ? 'tag ok' : 'tag bad'">
                {{ row[column] }}
              </span>
              <span v-else>{{ row[column] ?? '—' }}</span>
            </td>
          </tr>
          <tr v-if="!rectifiers.length">
            <td :colspan="rectifierColumns.length" class="empty-state">暂无恒电位仪采集数据</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 批次导入 -->
    <div v-if="activeTab === 'import'" class="import-panel">
      <form class="filter-bar import-form" @submit.prevent="submitImport">
        <label class="filter-item">
          <span>批次号</span>
          <input v-model="batchNo" placeholder="留空则按导入时间生成" />
        </label>
        <button class="btn primary" type="submit">开始导入</button>
        <button class="btn ghost" type="button" @click="fillSample">填入示例数据</button>
        <button class="btn ghost" type="button" @click="clearInput">清空</button>
      </form>
      <p class="field-hint">
        每行一条读数，首行为表头，可用 Excel 直接粘贴；列：测点编号、恒电位仪编号、参比电极编号、采集时间、保护电位(V)。
        有效保护电位区间 -1.20V ~ -0.85V（CSE）。校验不通过的行会单独列出原因，已通过的行照常入库。
      </p>
      <textarea
        v-model="importText"
        class="import-textarea"
        rows="10"
        placeholder="测点编号&#10;CP-01-A&#10;..."
      ></textarea>

      <div v-if="importResult" class="import-result">
        <h3>导入结果：{{ importResult['批次号'] }}</h3>
        <div class="stat-row">
          <article class="stat-card">
            <span class="stat-label">总行数</span>
            <strong class="stat-value">{{ importResult['总行数'] }}</strong>
          </article>
          <article class="stat-card">
            <span class="stat-label">导入成功</span>
            <strong class="stat-value">{{ importResult['导入成功'] }}</strong>
          </article>
          <article class="stat-card">
            <span class="stat-label">新增 / 覆盖</span>
            <strong class="stat-value">{{ importResult['新增'] }} / {{ importResult['覆盖'] }}</strong>
          </article>
          <article class="stat-card">
            <span class="stat-label">失败行数</span>
            <strong class="stat-value" :class="importResult['失败'] ? 'text-bad' : ''">{{ importResult['失败'] }}</strong>
          </article>
          <article class="stat-card">
            <span class="stat-label">分组数（恒电位仪/参比电极）</span>
            <strong class="stat-value">{{ importResult['分组数'] }}</strong>
          </article>
        </div>
        <ul class="group-list">
          <li v-for="group in importResult['分组明细']" :key="group['分组']">
            {{ group['分组'] }}：{{ group['行数'] }} 条
          </li>
        </ul>
        <table v-if="importResult['失败行'].length" class="data-table fail-table">
          <thead>
            <tr>
              <th v-for="column in failColumns" :key="column">{{ column }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="fail in importResult['失败行']" :key="String(fail['行号'])">
              <td v-for="column in failColumns" :key="column" :class="column === '原因' ? 'reason-cell' : ''">
                {{ fail[column] ?? '—' }}
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else class="ok-text">本批全部行校验通过，无失败记录。</p>
      </div>
    </div>

    <!-- 台账历史读数 -->
    <div v-if="activeTab === 'ledger'">
      <form class="filter-bar" @submit.prevent="reloadReadings">
        <label class="filter-item">
          <span>测点编号</span>
          <input v-model="readingFilters.point" placeholder="按测点编号检索" />
        </label>
        <label class="filter-item">
          <span>恒电位仪</span>
          <input v-model="readingFilters.rectifier" placeholder="按恒电位仪编号" />
        </label>
        <label class="filter-item">
          <span>参比电极</span>
          <input v-model="readingFilters.electrode" placeholder="按参比电极编号" />
        </label>
        <label class="filter-item">
          <span>采集结论</span>
          <select v-model="readingFilters.conclusion">
            <option value="">全部</option>
            <option v-for="item in conclusions" :key="item" :value="item">{{ item }}</option>
          </select>
        </label>
        <button class="btn" type="submit">查询</button>
        <button class="btn ghost" type="button" @click="resetReadingFilters">重置条件</button>
      </form>
      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in readingColumns" :key="column">{{ column }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in readings" :key="String(row.id)">
            <td v-for="column in readingColumns" :key="column">
              <span v-if="column === '采集结论'" :class="row[column] === '保护达标' ? 'tag ok' : 'tag bad'">
                {{ row[column] ?? '—' }}
              </span>
              <span v-else-if="column === '批次号'">
                {{ row[column] }}
                <em v-if="row[column] === '存量回填'" class="legacy-flag">存量回填</em>
              </span>
              <span v-else>{{ row[column] ?? '—' }}</span>
            </td>
          </tr>
          <tr v-if="!readings.length">
            <td :colspan="readingColumns.length" class="empty-state">暂无台账读数，可先进行批次导入</td>
          </tr>
        </tbody>
      </table>
      <footer class="page-foot">
        <span>共 {{ readingTotal }} 条台账读数（按采集时间倒序，含存量回填历史条目）</span>
        <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      </footer>
    </div>

    <!-- 防腐层检查统计 -->
    <div v-if="activeTab === 'stats'">
      <div class="stat-row">
        <article class="stat-card">
          <span class="stat-label">台账读数总条数</span>
          <strong class="stat-value">{{ statsSummary['台账读数总条数'] ?? 0 }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">达标 / 欠保护 / 过保护</span>
          <strong class="stat-value">
            {{ statsSummary['达标条数'] ?? 0 }} / {{ statsSummary['欠保护条数'] ?? 0 }} / {{ statsSummary['过保护条数'] ?? 0 }}
          </strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">防腐层检查次数</span>
          <strong class="stat-value">{{ statsSummary['防腐层检查次数'] ?? 0 }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">破损处数合计</span>
          <strong class="stat-value">{{ statsSummary['防腐层破损处数合计'] ?? 0 }}</strong>
        </article>
      </div>

      <h3 class="block-title">按恒电位仪分组统计（读数条数与台账一致）</h3>
      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in statsColumns" :key="column">{{ column }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in statsGroups" :key="String(row['恒电位仪编号'])">
            <td v-for="column in statsColumns" :key="column">{{ row[column] ?? '—' }}</td>
          </tr>
          <tr v-if="!statsGroups.length">
            <td :colspan="statsColumns.length" class="empty-state">暂无统计数据</td>
          </tr>
        </tbody>
        <tfoot>
          <tr class="sum-row">
            <td>合计</td>
            <td>{{ statsSummary['台账读数总条数'] ?? 0 }}</td>
            <td>{{ statsSummary['达标条数'] ?? 0 }}</td>
            <td>{{ statsSummary['欠保护条数'] ?? 0 }}</td>
            <td>{{ statsSummary['过保护条数'] ?? 0 }}</td>
            <td>{{ statsSummary['防腐层检查次数'] ?? 0 }}</td>
            <td>{{ statsSummary['防腐层破损处数合计'] ?? 0 }}</td>
            <td>—</td>
          </tr>
        </tfoot>
      </table>

      <h3 class="block-title">防腐层状况等级分布</h3>
      <div class="grade-row">
        <span v-for="grade in gradeDist" :key="grade['防腐层状况等级']" class="grade-chip">
          {{ grade['防腐层状况等级'] }}：{{ grade['次数'] }} 次
        </span>
        <span v-if="!gradeDist.length" class="empty-state">暂无防腐层检查记录</span>
      </div>

      <h3 class="block-title">防腐层检查记录</h3>
      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in coatingColumns" :key="column">{{ column }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in coatingRows" :key="String(row.id)">
            <td v-for="column in coatingColumns" :key="column">{{ row[column] ?? '—' }}</td>
          </tr>
          <tr v-if="!coatingRows.length">
            <td :colspan="coatingColumns.length" class="empty-state">暂无防腐层检查记录</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
interface ImportResult {
  批次号: string
  总行数: number
  导入成功: number
  新增: number
  覆盖: number
  失败: number
  分组数: number
  分组明细: Array<Record<string, string | number>>
  失败行: Row[]
}

const ENDPOINT = '/api/cathodic'

const tabs = [
  { key: 'overview', label: '恒电位仪总览' },
  { key: 'import', label: '批次导入' },
  { key: 'ledger', label: '台账读数' },
  { key: 'stats', label: '防腐层检查统计' },
]
const activeTab = ref('overview')

const rectifierColumns = ['恒电位仪编号', '最近采集时间', '点位数', '达标点位数', '异常点位数', '机组结论', '防腐层检查日期', '防腐层状况等级', '防腐层破损处数', '防腐层检查意见']
const rectifiers = ref<Row[]>([])
const healthyCount = ref(0)

const readingColumns = ['测点编号', '恒电位仪编号', '参比电极编号', '采集时间', '保护电位(V)', '采集结论', '批次号', '导入时间']
const conclusions = ['保护达标', '欠保护（电位正于-0.85V）', '过保护（电位负于-1.20V）']
const readings = ref<Row[]>([])
const readingTotal = ref(0)
const readingFilters = reactive({ point: '', rectifier: '', electrode: '', conclusion: '' })
const errorMessage = ref('')

const batchNo = ref('')
const importText = ref('')
const importResult = ref<ImportResult | null>(null)
const failColumns = ['行号', '测点编号', '恒电位仪编号', '参比电极编号', '采集时间', '保护电位(V)', '原因']

const statsColumns = ['恒电位仪编号', '台账读数条数', '达标条数', '欠保护条数', '过保护条数', '防腐层检查次数', '防腐层破损处数合计', '最近防腐层等级']
const statsSummary = ref<Record<string, number>>({})
const statsGroups = ref<Row[]>([])
const gradeDist = ref<Array<Record<string, string | number>>>([])
const coatingColumns = ['恒电位仪编号', '检查日期', '防腐层状况等级', '破损处数', '检查意见', '检查人员']
const coatingRows = ref<Row[]>([])

function parseTsv(text: string): Row[] {
  const lines = text.split(/\r?\n/).map(line => line.trim()).filter(Boolean)
  if (lines.length < 2) {
    return []
  }
  const headers = lines[0].split('\t').map(item => item.trim())
  return lines.slice(1).map(line => {
    const cells = line.split('\t').map(item => item.trim())
    const row: Row = {}
    headers.forEach((header, index) => {
      row[header] = cells[index] ?? ''
    })
    return row
  })
}

function fillSample() {
  batchNo.value = batchNo.value || `BATCH-${new Date().toISOString().slice(0, 10).replace(/-/g, '')}`
  importText.value = [
    '测点编号\t恒电位仪编号\t参比电极编号\t采集时间\t保护电位(V)',
    'CP-01-A\tRECT-01\tREF-01\t2026-09-28 09:00\t-0.96',
    'CP-01-B\tRECT-01\tREF-01\t2026-09-28 09:05\t-0.80',
    'CP-02-A\tRECT-02\tREF-02\t2026-09-28 09:10\t-1.28',
    'CP-03-A\tRECT-03\tREF-03\t2026-09-28 09:15\t-1.02',
    'CP-05-A\tRECT-05\t\t2026-09-28 09:20\t-0.93',
  ].join('\n')
}

function clearInput() {
  importText.value = ''
  importResult.value = null
  errorMessage.value = ''
}

async function submitImport() {
  errorMessage.value = ''
  const rows = parseTsv(importText.value)
  if (!rows.length) {
    errorMessage.value = '未解析到任何数据行，请粘贴含表头的多行采集数据（Tab 分隔）'
    return
  }
  try {
    const response = await request(`${ENDPOINT}/import`, {
      method: 'POST',
      body: JSON.stringify({ batch_no: batchNo.value, rows }),
    })
    if (!response.ok) {
      const payload = await response.json().catch(() => null)
      throw new Error(payload?.detail ?? '批次导入失败')
    }
    importResult.value = await response.json()
    await Promise.all([loadRectifiers(), loadStats()])
    if (activeTab.value === 'ledger') {
      await reloadReadings()
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '批次导入失败'
  }
}

async function loadRectifiers() {
  const response = await request(`${ENDPOINT}/rectifiers`)
  if (!response.ok) {
    throw new Error('恒电位仪总览读取失败')
  }
  const payload = await response.json()
  rectifiers.value = payload.items ?? []
  healthyCount.value = rectifiers.value.filter(item => item['机组结论'] === '保护达标').length
}

async function reloadReadings() {
  errorMessage.value = ''
  const query = new URLSearchParams(
    Object.entries(readingFilters).filter(([, value]) => value) as [string, string][],
  ).toString()
  try {
    const response = await request(`${ENDPOINT}/readings?size=200&${query}`)
    if (!response.ok) {
      throw new Error('台账读数读取失败')
    }
    const payload = await response.json()
    readings.value = payload.items ?? []
    readingTotal.value = payload.total ?? readings.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '台账读数读取失败'
  }
}

function resetReadingFilters() {
  Object.assign(readingFilters, { point: '', rectifier: '', electrode: '', conclusion: '' })
  void reloadReadings()
}

async function loadStats() {
  const response = await request(`${ENDPOINT}/coating/stats`)
  if (!response.ok) {
    throw new Error('防腐层统计读取失败')
  }
  const payload = await response.json()
  statsSummary.value = payload['汇总'] ?? {}
  statsGroups.value = payload['分组统计'] ?? []
  gradeDist.value = payload['等级分布'] ?? []
  coatingRows.value = payload['防腐层检查记录'] ?? []
}

async function switchTab(key: string) {
  activeTab.value = key
  try {
    if (key === 'overview') {
      await loadRectifiers()
    } else if (key === 'ledger') {
      await reloadReadings()
    } else if (key === 'stats') {
      await loadStats()
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '数据加载失败'
  }
}

onMounted(loadRectifiers)
</script>

<style scoped>
.tab-bar {
  display: flex;
  gap: 8px;
  margin: 12px 0 16px;
}
.tab-item {
  border: 1px solid var(--border-color, #d9dee5);
  background: #fff;
  border-radius: 6px;
  padding: 6px 16px;
  cursor: pointer;
  color: #4b5563;
}
.tab-item.active {
  background: #1d6fe0;
  border-color: #1d6fe0;
  color: #fff;
}
.import-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.import-form {
  align-items: flex-end;
}
.field-hint {
  color: #6b7280;
  font-size: 13px;
  margin: 0;
}
.import-textarea {
  width: 100%;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13px;
  padding: 10px;
  border: 1px solid #d9dee5;
  border-radius: 6px;
  resize: vertical;
}
.import-result {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 14px;
  background: #fafbfc;
}
.group-list {
  margin: 8px 0 12px;
  padding-left: 18px;
  color: #4b5563;
  font-size: 13px;
}
.fail-table .reason-cell {
  color: #c0392b;
}
.ok-text {
  color: #1a8a4d;
}
.tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
}
.tag.ok {
  background: #e6f7ee;
  color: #1a8a4d;
}
.tag.bad {
  background: #fdecea;
  color: #c0392b;
}
.text-bad {
  color: #c0392b;
}
.legacy-flag {
  margin-left: 6px;
  font-style: normal;
  font-size: 12px;
  color: #92600a;
  background: #fdf4dc;
  border-radius: 4px;
  padding: 0 6px;
}
.block-title {
  margin: 18px 0 8px;
  font-size: 15px;
}
.grade-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.grade-chip {
  background: #eef3fb;
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 13px;
  color: #2c4a7c;
}
.sum-row td {
  font-weight: 600;
  background: #f6f8fb;
}
[v-cloak] {
  display: none;
}
</style>
