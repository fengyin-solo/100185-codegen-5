<template>
  <section class="page" data-module="cathodic">
    <header class="page-head">
      <div>
        <h2>管网阴极保护监测台账</h2>
        <p class="page-desc">
          保护电位按批次导入，按参比电极与恒电位仪分组逐条校验（有效区间 -1.20V ～ -0.85V vs CSE）；
          同一测点按采集时间覆盖，重复导入不产生新记录。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="switchTab('import')">批次导入</button>
      </div>
    </header>

    <div class="tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab"
        :class="{ active: activeTab === tab.key }"
        type="button"
        @click="switchTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- 恒电位仪台账：最近采集结论 + 防腐层检查情况 -->
    <div v-if="activeTab === 'rectifiers'">
      <div class="stat-row">
        <article class="stat-card">
          <span class="stat-label">恒电位仪总数</span>
          <strong class="stat-value">{{ rectifiers.length }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">最近采集异常</span>
          <strong class="stat-value">{{ rectifierAbnormalCount }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">防腐层待整改</span>
          <strong class="stat-value">{{ coatingPendingCount }}</strong>
        </article>
      </div>
      <table class="data-table">
        <thead>
          <tr>
            <th>恒电位仪编号</th><th>名称</th><th>所在管段</th><th>规格型号</th><th>责任班组</th>
            <th>最近采集时间</th><th>最近保护电位(V)</th><th>最近采集结论</th>
            <th>防腐层检查日期</th><th>防腐层检查结论</th><th>破损点数</th><th>检查情况</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rectifiers" :key="String(row.id)">
            <td>{{ row['恒电位仪编号'] }}</td>
            <td>{{ row['恒电位仪名称'] }}</td>
            <td>{{ row['所在管段'] }}</td>
            <td>{{ row['规格型号'] }}</td>
            <td>{{ row['责任班组'] }}</td>
            <td>{{ row['最近采集时间'] ?? '—' }}</td>
            <td>{{ row['最近保护电位(V)'] ?? '—' }}</td>
            <td><span class="badge" :class="conclusionClass(row['最近采集结论'])">{{ row['最近采集结论'] }}</span></td>
            <td>{{ row['最近检查日期'] ?? '—' }}</td>
            <td><span class="badge" :class="coatingClass(row['防腐层检查结论'])">{{ row['防腐层检查结论'] }}</span></td>
            <td>{{ row['破损点数'] }}</td>
            <td class="cell-note">{{ row['防腐层检查情况'] }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 采集台账 -->
    <div v-else-if="activeTab === 'readings'">
      <form class="filter-bar" @submit.prevent="reloadReadings">
        <label class="filter-item">
          <span>批次号</span>
          <input v-model="readingFilters.batch_no" placeholder="按批次号检索" />
        </label>
        <label class="filter-item">
          <span>测点编号</span>
          <input v-model="readingFilters.point" placeholder="按测点检索" />
        </label>
        <label class="filter-item">
          <span>恒电位仪</span>
          <select v-model="readingFilters.rectifier">
            <option value="">全部</option>
            <option v-for="r in masterRectifiers" :key="String(r['恒电位仪编号'])" :value="String(r['恒电位仪编号'])">{{ r['恒电位仪编号'] }}</option>
          </select>
        </label>
        <label class="filter-item">
          <span>参比电极</span>
          <select v-model="readingFilters.electrode">
            <option value="">全部</option>
            <option v-for="e in masterElectrodes" :key="String(e['参比电极编号'])" :value="String(e['参比电极编号'])">{{ e['参比电极编号'] }}</option>
          </select>
        </label>
        <label class="filter-item">
          <span>采集结论</span>
          <select v-model="readingFilters.conclusion">
            <option value="">全部</option>
            <option value="保护合格">保护合格</option>
            <option value="欠保护">欠保护</option>
            <option value="过保护">过保护</option>
          </select>
        </label>
        <button class="btn" type="submit">查询</button>
        <button class="btn ghost" type="button" @click="resetReadingFilters">重置</button>
      </form>
      <table class="data-table">
        <thead>
          <tr>
            <th>批次号</th><th>测点编号</th><th>恒电位仪编号</th><th>参比电极编号</th>
            <th>采集时间</th><th>保护电位(V)</th><th>采集结论</th><th>采集人员</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in readings" :key="String(row.id)">
            <td>{{ row['批次号'] }}</td>
            <td>{{ row['测点编号'] }}</td>
            <td>{{ row['恒电位仪编号'] }}</td>
            <td>{{ row['参比电极编号'] }}</td>
            <td>{{ row['采集时间'] }}</td>
            <td>{{ row['保护电位(V)'] }}</td>
            <td><span class="badge" :class="conclusionClass(row['采集结论'])">{{ row['采集结论'] }}</span></td>
            <td>{{ row['采集人员'] || '—' }}</td>
          </tr>
          <tr v-if="!readings.length">
            <td colspan="8" class="empty-state">暂无符合条件的读数，可到「批次导入」页签导入现场数据</td>
          </tr>
        </tbody>
      </table>
      <footer class="page-foot"><span>共 {{ readingTotal }} 条台账读数</span></footer>
    </div>

    <!-- 历史条目 -->
    <div v-else-if="activeTab === 'history'">
      <form class="filter-bar" @submit.prevent="reloadHistory">
        <label class="filter-item">
          <span>测点编号</span>
          <input v-model="historyPoint" placeholder="留空查看全部测点" />
        </label>
        <button class="btn" type="submit">查询</button>
        <button class="btn ghost" type="button" @click="historyPoint = ''; reloadHistory()">全部测点</button>
      </form>
      <h3 class="block-title">测点汇总（{{ historyPoints.length }} 个测点）</h3>
      <table class="data-table compact">
        <thead>
          <tr><th>测点编号</th><th>恒电位仪</th><th>参比电极</th><th>历史条数</th><th>首次采集时间</th><th>最近采集时间</th><th>最近电位(V)</th><th>最近结论</th></tr>
        </thead>
        <tbody>
          <tr v-for="p in historyPoints" :key="p['测点编号']">
            <td><button class="link" type="button" @click="selectHistoryPoint(p['测点编号'])">{{ p['测点编号'] }}</button></td>
            <td>{{ p['恒电位仪编号'] }}</td>
            <td>{{ p['参比电极编号'] }}</td>
            <td>{{ p['历史条数'] }}</td>
            <td>{{ p['首次采集时间'] }}</td>
            <td>{{ p['最近采集时间'] }}</td>
            <td>{{ p['最近电位'] }}</td>
            <td><span class="badge" :class="conclusionClass(p['最近结论'])">{{ p['最近结论'] }}</span></td>
          </tr>
        </tbody>
      </table>
      <h3 class="block-title">历史条目（按采集时间升序，共 {{ historyRows.length }} 条）</h3>
      <table class="data-table compact">
        <thead>
          <tr><th>测点编号</th><th>采集时间</th><th>保护电位(V)</th><th>采集结论</th><th>批次号</th><th>恒电位仪</th><th>参比电极</th></tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in historyRows" :key="`${row['测点编号']}-${row['采集时间']}-${idx}`">
            <td>{{ row['测点编号'] }}</td>
            <td>{{ row['采集时间'] }}</td>
            <td>{{ row['保护电位(V)'] }}</td>
            <td><span class="badge" :class="conclusionClass(row['采集结论'])">{{ row['采集结论'] }}</span></td>
            <td>{{ row['批次号'] }}</td>
            <td>{{ row['恒电位仪编号'] }}</td>
            <td>{{ row['参比电极编号'] }}</td>
          </tr>
          <tr v-if="!historyRows.length"><td colspan="7" class="empty-state">该测点暂无历史条目</td></tr>
        </tbody>
      </table>
    </div>

    <!-- 防腐层检查 -->
    <div v-else-if="activeTab === 'coatings'">
      <table class="data-table">
        <thead>
          <tr>
            <th>检查单号</th><th>恒电位仪编号</th><th>检查日期</th><th>防腐层类型</th>
            <th>绝缘电阻(MΩ·m²)</th><th>破损点数</th><th>检查情况</th><th>检查人员</th><th>检查结论</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in coatings" :key="String(row.id)">
            <td>{{ row['检查单号'] }}</td>
            <td>{{ row['恒电位仪编号'] }}</td>
            <td>{{ row['检查日期'] }}</td>
            <td>{{ row['防腐层类型'] }}</td>
            <td>{{ row['绝缘电阻(MΩ·m²)'] }}</td>
            <td>{{ row['破损点数'] }}</td>
            <td class="cell-note">{{ row['检查情况'] }}</td>
            <td>{{ row['检查人员'] }}</td>
            <td><span class="badge" :class="coatingClass(row['检查结论'])">{{ row['检查结论'] }}</span></td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 防腐层检查统计：读数台账聚合，条数一致 -->
    <div v-else-if="activeTab === 'stats'">
      <div class="stat-row">
        <article class="stat-card">
          <span class="stat-label">台账读数条数</span>
          <strong class="stat-value">{{ stats.reading['台账读数条数'] ?? 0 }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">保护合格</span>
          <strong class="stat-value ok-text">{{ stats.reading['合格条数'] ?? 0 }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">欠保护</span>
          <strong class="stat-value warn-text">{{ stats.reading['欠保护条数'] ?? 0 }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">过保护</span>
          <strong class="stat-value warn-text">{{ stats.reading['过保护条数'] ?? 0 }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">合格率</span>
          <strong class="stat-value">{{ stats.reading['合格率'] ?? '—' }}</strong>
        </article>
      </div>
      <div class="stat-row">
        <article class="stat-card">
          <span class="stat-label">防腐层检查记录</span>
          <strong class="stat-value">{{ stats.coating['检查记录数'] ?? 0 }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">待整改检查</span>
          <strong class="stat-value warn-text">{{ stats.coating['待整改数'] ?? 0 }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">破损点合计</span>
          <strong class="stat-value warn-text">{{ stats.coating['破损点数合计'] ?? 0 }}</strong>
        </article>
      </div>
      <h3 class="block-title">分恒电位仪统计</h3>
      <table class="data-table">
        <thead>
          <tr>
            <th>恒电位仪编号</th><th>台账读数条数</th><th>合格</th><th>欠保护</th><th>过保护</th>
            <th>合格率</th><th>防腐层检查次数</th><th>破损点合计</th><th>待整改检查</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in stats.devices" :key="d['恒电位仪编号']">
            <td>{{ d['恒电位仪编号'] }}</td>
            <td>{{ d['台账读数条数'] }}</td>
            <td>{{ d['合格条数'] }}</td>
            <td>{{ d['欠保护条数'] }}</td>
            <td>{{ d['过保护条数'] }}</td>
            <td>{{ d['合格率'] }}</td>
            <td>{{ d['防腐层检查次数'] }}</td>
            <td>{{ d['破损点数合计'] }}</td>
            <td>{{ d['待整改检查数'] }}</td>
          </tr>
        </tbody>
      </table>
      <p class="reconcile">{{ stats.note }}</p>
    </div>

    <!-- 批次导入 -->
    <div v-else-if="activeTab === 'import'" class="import-pane">
      <div class="import-guide">
        <h3 class="block-title">导入说明</h3>
        <ul class="hint-list">
          <li>CSV 列：{{ templateColumns.join('、') }}（首行为表头，编码 UTF-8）。</li>
          <li>有效范围：{{ templateRange[0] }}V ～ {{ templateRange[1] }}V（相对 Cu/CuSO4 参比电极）；支持 mV 写法，如 -950。</li>
          <li>导入按「恒电位仪 × 参比电极」分组校验；缺字段、设备未登记、电位无法解析的行单独列出原因，不影响其余行入库。</li>
          <li>超出有效区间的读数按「欠保护/过保护」入库并标异常；同一测点按采集时间覆盖，重复导入同一批不会多出记录。</li>
        </ul>
        <button class="btn ghost" type="button" @click="downloadTemplate">下载 CSV 模板</button>
      </div>

      <form class="import-form" @submit.prevent="submitImport">
        <label class="filter-item">
          <span>批次号（留空自动生成）</span>
          <input v-model="batchNo" placeholder="如 B202609200900" />
        </label>
        <label class="filter-item file-item">
          <span>选择 CSV 文件</span>
          <input type="file" accept=".csv,.txt" @change="onFileChange" />
        </label>
        <button class="btn primary" type="submit" :disabled="!csvText">导入本批数据</button>
      </form>

      <details class="paste-box" :open="!csvText">
        <summary>或直接粘贴 CSV 文本（含表头）</summary>
        <textarea v-model="csvText" rows="6" :placeholder="csvPlaceholder"></textarea>
      </details>

      <p v-if="importError" class="error-text">{{ importError }}</p>

      <div v-if="importResult" class="import-result">
        <h3 class="block-title">导入结果（批次 {{ importResult['批次号'] }}）</h3>
        <div class="stat-row">
          <article class="stat-card"><span class="stat-label">总行数</span><strong class="stat-value">{{ importResult['总行数'] }}</strong></article>
          <article class="stat-card"><span class="stat-label">通过入库</span><strong class="stat-value ok-text">{{ importResult['通过行数'] }}</strong></article>
          <article class="stat-card"><span class="stat-label">其中异常标记</span><strong class="stat-value warn-text">{{ importResult['异常入库行数'] }}</strong></article>
          <article class="stat-card"><span class="stat-label">失败行</span><strong class="stat-value err-text">{{ importResult['失败行数'] }}</strong></article>
          <article class="stat-card"><span class="stat-label">新增 / 覆盖</span><strong class="stat-value">{{ importResult['新增条数'] }} / {{ importResult['覆盖条数'] }}</strong></article>
          <article class="stat-card"><span class="stat-label">台账总条数</span><strong class="stat-value">{{ importResult['台账总条数'] }}</strong></article>
        </div>

        <h4 class="block-title">分组校验（恒电位仪 × 参比电极）</h4>
        <table class="data-table compact">
          <thead>
            <tr><th>恒电位仪编号</th><th>参比电极编号</th><th>通过条数</th><th>合格</th><th>欠保护</th><th>过保护</th></tr>
          </thead>
          <tbody>
            <tr v-for="g in importResult['分组统计']" :key="`${g['恒电位仪编号']}-${g['参比电极编号']}`">
              <td>{{ g['恒电位仪编号'] }}</td>
              <td>{{ g['参比电极编号'] }}</td>
              <td>{{ g['通过条数'] }}</td>
              <td>{{ g['合格条数'] }}</td>
              <td>{{ g['欠保护条数'] }}</td>
              <td>{{ g['过保护条数'] }}</td>
            </tr>
            <tr v-if="!importResult['分组统计'].length"><td colspan="6" class="empty-state">本批没有可入库的行</td></tr>
          </tbody>
        </table>

        <template v-if="importResult['异常明细'].length">
          <h4 class="block-title warn-text">已入库但不达标（{{ importResult['异常明细'].length }} 行）</h4>
          <table class="data-table compact">
            <thead><tr><th>行号</th><th>测点编号</th><th>恒电位仪</th><th>保护电位(V)</th><th>采集结论</th><th>原因</th></tr></thead>
            <tbody>
              <tr v-for="w in importResult['异常明细']" :key="`w-${w['行号']}`">
                <td>{{ w['行号'] }}</td><td>{{ w['测点编号'] }}</td><td>{{ w['恒电位仪编号'] }}</td>
                <td>{{ w['保护电位(V)'] }}</td>
                <td><span class="badge" :class="conclusionClass(w['采集结论'])">{{ w['采集结论'] }}</span></td>
                <td class="cell-note">{{ w['原因'] }}</td>
              </tr>
            </tbody>
          </table>
        </template>

        <template v-if="importResult['失败明细'].length">
          <h4 class="block-title err-text">失败行（{{ importResult['失败明细'].length }} 行，未入库）</h4>
          <table class="data-table compact">
            <thead><tr><th>行号</th><th>原因</th><th>原始数据</th></tr></thead>
            <tbody>
              <tr v-for="f in importResult['失败明细']" :key="`f-${f['行号']}`">
                <td>{{ f['行号'] }}</td>
                <td class="cell-note err-text">{{ f['原因'] }}</td>
                <td class="cell-note">{{ formatRaw(f['原始数据']) }}</td>
              </tr>
            </tbody>
          </table>
        </template>
      </div>
    </div>

    <footer class="page-foot">
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span>阴极保护监测台账 · 数据来源为现场批次导入</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type Page<T> = { items: T[]; total: number }
type ImportResult = {
  批次号: string
  总行数: number
  通过行数: number
  失败行数: number
  异常入库行数: number
  新增条数: number
  覆盖条数: number
  批内重复条数: number
  台账总条数: number
  失败明细: { 行号: number; 原因: string; 原始数据: Row }[]
  异常明细: { 行号: number; 测点编号: string; 恒电位仪编号: string; '保护电位(V)': string; 采集结论: string; 原因: string }[]
  分组统计: { 恒电位仪编号: string; 参比电极编号: string; 通过条数: number; 合格条数: number; 欠保护条数: number; 过保护条数: number }[]
}
type StatsPayload = {
  读数统计: Record<string, number | string>
  防腐层检查统计: Record<string, number>
  分恒电位仪统计: Record<string, number | string>[]
  对账说明: string
}

const tabs = [
  { key: 'rectifiers', label: '恒电位仪台账' },
  { key: 'readings', label: '采集台账' },
  { key: 'history', label: '历史条目' },
  { key: 'coatings', label: '防腐层检查' },
  { key: 'stats', label: '防腐层检查统计' },
  { key: 'import', label: '批次导入' },
] as const

const activeTab = ref<(typeof tabs)[number]['key']>('rectifiers')
const errorMessage = ref('')

const rectifiers = ref<Row[]>([])
const readings = ref<Row[]>([])
const readingTotal = ref(0)
const historyRows = ref<Row[]>([])
const historyPoints = ref<Record<string, string | number>[]>([])
const coatings = ref<Row[]>([])
const masterRectifiers = ref<Row[]>([])
const masterElectrodes = ref<Row[]>([])

const readingFilters = ref<Record<string, string>>({ batch_no: '', point: '', rectifier: '', electrode: '', conclusion: '' })
const historyPoint = ref('')

const stats = ref<{ reading: Record<string, number | string>; coating: Record<string, number>; devices: Record<string, number | string>[]; note: string }>({
  reading: {},
  coating: {},
  devices: [],
  note: '',
})

const templateColumns = ref<string[]>(['测点编号', '恒电位仪编号', '参比电极编号', '采集时间', '保护电位', '采集人员'])
const templateRange = ref<[number, number]>([-1.2, -0.85])
const batchNo = ref('')
const csvText = ref('')
const importError = ref('')
const importResult = ref<ImportResult | null>(null)

const csvPlaceholder = computed(
  () => `${templateColumns.value.join(',')}\nCP-001,R-01,CSE-01,2026-09-20 10:00,-0.95,张三`,
)

const rectifierAbnormalCount = computed(
  () => rectifiers.value.filter((r) => r['最近采集结论'] === '欠保护' || r['最近采集结论'] === '过保护').length,
)
const coatingPendingCount = computed(
  () => rectifiers.value.filter((r) => r['防腐层检查结论'] === '不合格' || r['防腐层检查结论'] === '限期整改').length,
)

function conclusionClass(value: unknown): string {
  if (value === '保护合格') return 'badge-ok'
  if (value === '欠保护' || value === '过保护') return 'badge-warn'
  return 'badge-muted'
}
function coatingClass(value: unknown): string {
  if (value === '合格') return 'badge-ok'
  if (value === '未检查' || value === '不合格' || value === '限期整改') return 'badge-warn'
  return 'badge-muted'
}

async function getJson<T>(path: string): Promise<T> {
  const response = await request(path)
  if (!response.ok) throw new Error(`接口返回 ${response.status}`)
  return (await response.json()) as T
}

async function loadRectifiers() {
  const payload = await getJson<{ items: Row[] }>('/api/cathodic/rectifiers')
  rectifiers.value = payload.items
}
async function loadCoatings() {
  const payload = await getJson<{ items: Row[] }>('/api/cathodic/coatings')
  coatings.value = payload.items
}
async function loadMaster() {
  const payload = await getJson<{ rectifiers: Row[]; electrodes: Row[] }>('/api/cathodic/master')
  masterRectifiers.value = payload.rectifiers
  masterElectrodes.value = payload.electrodes
}
async function loadTemplateMeta() {
  const payload = await getJson<{ columns: string[]; valid_range_v: [number, number] }>('/api/cathodic/import/template')
  templateColumns.value = payload.columns
  templateRange.value = payload.valid_range_v as [number, number]
}
async function reloadReadings() {
  const params = new URLSearchParams()
  Object.entries(readingFilters.value).forEach(([key, value]) => {
    if (value) params.set(key, value)
  })
  params.set('size', '500')
  const payload = await getJson<Page<Row>>(`/api/cathodic/readings?${params.toString()}`)
  readings.value = payload.items
  readingTotal.value = payload.total
}
async function reloadHistory() {
  const params = new URLSearchParams()
  if (historyPoint.value) params.set('point', historyPoint.value)
  const payload = await getJson<{ items: Row[]; points: Record<string, string | number>[] }>(`/api/cathodic/history?${params.toString()}`)
  historyRows.value = payload.items
  historyPoints.value = payload.points
}
async function loadStats() {
  const payload = await getJson<StatsPayload>('/api/cathodic/stats')
  stats.value = {
    reading: payload['读数统计'],
    coating: payload['防腐层检查统计'],
    devices: payload['分恒电位仪统计'],
    note: payload['对账说明'],
  }
}

function resetReadingFilters() {
  readingFilters.value = { batch_no: '', point: '', rectifier: '', electrode: '', conclusion: '' }
  void reloadReadings()
}

function selectHistoryPoint(value: string | number) {
  historyPoint.value = String(value)
  void reloadHistory()
}

function switchTab(key: (typeof tabs)[number]['key']) {
  activeTab.value = key
  errorMessage.value = ''
  void refreshActive()
}

async function refreshActive() {
  try {
    if (activeTab.value === 'rectifiers') await loadRectifiers()
    else if (activeTab.value === 'readings') await reloadReadings()
    else if (activeTab.value === 'history') await reloadHistory()
    else if (activeTab.value === 'coatings') await loadCoatings()
    else if (activeTab.value === 'stats') await loadStats()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '数据加载失败'
  }
}

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  importError.value = ''
  const reader = new FileReader()
  reader.onload = () => {
    csvText.value = String(reader.result ?? '').replace(/^﻿/, '')
  }
  reader.onerror = () => {
    importError.value = 'CSV 文件读取失败'
  }
  reader.readAsText(file, 'utf-8')
}

/** 解析带引号、转义双引号、CRLF 的 CSV。 */
function parseCsv(text: string): string[][] {
  const rows: string[][] = []
  let field = ''
  let row: string[] = []
  let inQuotes = false
  const src = text.replace(/^﻿/, '')
  for (let i = 0; i < src.length; i += 1) {
    const ch = src[i]
    if (inQuotes) {
      if (ch === '"') {
        if (src[i + 1] === '"') {
          field += '"'
          i += 1
        } else {
          inQuotes = false
        }
      } else {
        field += ch
      }
    } else if (ch === '"') {
      inQuotes = true
    } else if (ch === ',') {
      row.push(field)
      field = ''
    } else if (ch === '\n' || ch === '\r') {
      if (ch === '\r' && src[i + 1] === '\n') i += 1
      row.push(field)
      field = ''
      if (row.some((cell) => cell.trim() !== '')) rows.push(row)
      row = []
    } else {
      field += ch
    }
  }
  if (field !== '' || row.length) {
    row.push(field)
    if (row.some((cell) => cell.trim() !== '')) rows.push(row)
  }
  return rows
}

async function submitImport() {
  importError.value = ''
  importResult.value = null
  try {
    const parsed = parseCsv(csvText.value)
    if (parsed.length < 2) {
      importError.value = 'CSV 至少需要表头和一行数据'
      return
    }
    const headers = parsed[0].map((h) => h.trim())
    const rows = parsed.slice(1).map((cells) => {
      const record: Record<string, string> = {}
      headers.forEach((header, idx) => {
        record[header] = (cells[idx] ?? '').trim()
      })
      return record
    })
    const response = await request('/api/cathodic/import', {
      method: 'POST',
      body: JSON.stringify({ batch_no: batchNo.value || null, rows }),
    })
    if (!response.ok) throw new Error(`导入接口返回 ${response.status}`)
    importResult.value = (await response.json()) as ImportResult
    // 导入结果同时汇进统计与台账，刷新相关页签数据
    await Promise.all([loadRectifiers(), loadStats(), reloadReadings(), reloadHistory(), loadCoatings()])
  } catch (error) {
    importError.value = error instanceof Error ? error.message : '导入失败'
  }
}

function formatRaw(raw: Row): string {
  return Object.entries(raw)
    .filter(([, value]) => value !== '' && value !== null)
    .map(([key, value]) => `${key}=${value}`)
    .join('；')
}

function downloadTemplate() {
  const header = templateColumns.value.join(',')
  const sample = [
    'CP-R01-A,R-01,CSE-01,2026-09-20 10:00,-0.95,张三',
    'CP-R02-A,R-02,CSE-02,2026-09-20 10:30,-0.88,张三',
  ].join('\n')
  const blob = new Blob([`﻿${header}\n${sample}\n`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = '保护电位导入模板.csv'
  anchor.click()
  URL.revokeObjectURL(url)
}

onMounted(() => {
  void Promise.all([loadMaster(), loadTemplateMeta(), loadRectifiers()]).catch((error: unknown) => {
    errorMessage.value = error instanceof Error ? error.message : '台账初始化加载失败'
  })
})
</script>

<style scoped>
.tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border); margin-bottom: 12px; flex-wrap: wrap; }
.tab { border: none; background: none; padding: 8px 14px; cursor: pointer; font-size: 13px; color: var(--muted); border-bottom: 2px solid transparent; }
.tab.active { color: var(--brand); border-bottom-color: var(--brand); font-weight: 600; }
.badge { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 12px; }
.badge-ok { background: #e7f6ec; color: #1a7f37; }
.badge-warn { background: #fdecea; color: #b42318; }
.badge-muted { background: #eef2f6; color: var(--muted); }
.ok-text { color: #1a7f37; }
.warn-text { color: #b54708; }
.err-text { color: #b42318; }
.cell-note { max-width: 300px; color: #475569; }
.block-title { font-size: 14px; margin: 14px 0 8px; }
.compact th, .compact td { padding: 6px 8px; }
.reconcile { margin-top: 10px; font-size: 13px; color: var(--brand); }
.import-pane { display: flex; flex-direction: column; gap: 8px; }
.import-guide { background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; }
.hint-list { margin: 6px 0 10px; padding-left: 18px; color: #475569; font-size: 13px; line-height: 1.8; }
.import-form { display: flex; gap: 14px; align-items: flex-end; background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; }
.file-item input { font-size: 13px; }
.paste-box { background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 8px 14px; font-size: 13px; }
.paste-box textarea { width: 100%; margin-top: 8px; font-family: monospace; font-size: 12px; border: 1px solid var(--border); border-radius: 6px; padding: 8px; }
.import-result { margin-top: 8px; }
select { border: 1px solid var(--border); border-radius: 6px; padding: 5px 8px; font-size: 13px; }
</style>
