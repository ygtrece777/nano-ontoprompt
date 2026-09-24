import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, BarChart3, Database, Gauge, RefreshCw, ShieldAlert } from 'lucide-react'
import { apiClientV2 } from '@/api/client'

type Item = { name: string; count: number }
type Risk = { title: string; reason: string; severity: string; type: string }
type Analytics = {
  available: boolean
  totals: { rows: number; concepts: number; types: number; data_types?: number; ontology_entities?: number; edges: number }
  entity_types: Item[]
  ontology_entity_types?: Item[]
  relation_types?: Item[]
  status_breakdown: Item[]
  risk_items: Risk[]
  sources: Item[]
}

const colors = ['bg-blue-500', 'bg-emerald-500', 'bg-amber-500', 'bg-violet-500', 'bg-rose-500', 'bg-cyan-500']

function BarList({ items, empty }: { items: Item[]; empty: string }) {
  const max = Math.max(...items.map(item => item.count), 1)
  if (!items.length) return <p className="text-sm text-gray-400 py-5">{empty}</p>
  return <div className="space-y-3">
    {items.map((item, index) => (
      <div key={`${item.name}-${index}`}>
        <div className="flex justify-between text-sm mb-1">
          <span className="text-gray-700 truncate pr-3">{item.name}</span>
          <span className="font-medium text-gray-900 tabular-nums">{item.count}</span>
        </div>
        <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
          <div className={`h-full rounded-full ${colors[index % colors.length]}`} style={{ width: `${Math.max(4, item.count / max * 100)}%` }} />
        </div>
      </div>
    ))}
  </div>
}

export default function AnalyticsTab({ ontologyId }: { ontologyId: string }) {
  const { data, isLoading, isError, refetch, isFetching } = useQuery<Analytics>({
    queryKey: ['analytics', ontologyId],
    queryFn: () => apiClientV2.get(`/ontologies/${ontologyId}/analytics`) as any,
    staleTime: 30_000,
  })
  const [building, setBuilding] = useState(false)
  const [buildMessage, setBuildMessage] = useState('')

  const buildAllInstances = async () => {
    setBuilding(true); setBuildMessage('')
    try {
      const result: any = await apiClientV2.post(`/ontologies/${ontologyId}/mappings/build-all`)
      setBuildMessage(`全量构建完成：${result.instances_written ?? result.total_instances ?? 0} 条实例`)
      await refetch()
    } catch (err: any) {
      setBuildMessage(err?.detail || '当前本体没有可构建的映射数据')
    } finally { setBuilding(false) }
  }

  if (isLoading) return <div className="py-12 text-center text-gray-400">正在加载分析数据…</div>
  if (isError || !data) return <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-red-700">分析接口暂时不可用。<button onClick={() => refetch()} className="ml-3 underline">重试</button></div>

  const totals = data.totals
  const cards = [
    { label: '业务数据行', value: totals.rows, icon: Database, color: 'text-blue-600 bg-blue-50' },
    { label: '本体实体类型', value: totals.types, icon: BarChart3, color: 'text-violet-600 bg-violet-50' },
    { label: '图谱关系', value: totals.edges, icon: Gauge, color: 'text-emerald-600 bg-emerald-50' },
    { label: '风险记录', value: data.risk_items.length, icon: ShieldAlert, color: 'text-rose-600 bg-rose-50' },
  ]

  return <div className="space-y-6">
    <div className="flex items-center justify-between">
      <div><h3 className="text-lg font-semibold text-gray-900">数据分析</h3><p className="text-sm text-gray-500 mt-1">基于当前本体中的业务数据自动汇总</p></div>
      <div className="flex items-center gap-2"><button onClick={buildAllInstances} className="px-3 py-2 text-sm rounded-lg bg-black text-white hover:bg-gray-800 disabled:opacity-50" disabled={building}>{building ? '全量构建中…' : '构建全量实例'}</button><button onClick={() => refetch()} className="flex items-center gap-2 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50" disabled={isFetching}><RefreshCw size={14} className={isFetching ? 'animate-spin' : ''} />刷新</button></div>
    </div>
    {buildMessage && <div className="rounded-lg border border-blue-100 bg-blue-50 px-3 py-2 text-sm text-blue-700">{buildMessage}</div>}

    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map(({ label, value, icon: Icon, color }) => <div key={label} className="bg-white rounded-xl border p-4"><div className="flex items-center justify-between"><span className="text-sm text-gray-500">{label}</span><span className={`p-2 rounded-lg ${color}`}><Icon size={17} /></span></div><div className="mt-3 text-2xl font-semibold text-gray-900 tabular-nums">{value.toLocaleString()}</div></div>)}
    </div>

    <section className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <div className="bg-white rounded-xl border p-5"><h4 className="font-semibold mb-1">本体结构：实体类型分布</h4><p className="text-xs text-gray-400 mb-4">本体中定义的全部实体类型，不等同于业务数据行</p><BarList items={data.ontology_entity_types || []} empty="暂无本体实体类型" /></div>
      <div className="bg-white rounded-xl border p-5"><h4 className="font-semibold mb-4">领域分析：状态分布</h4><BarList items={data.status_breakdown} empty="暂无状态字段" /></div>
    </section>

    <section className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <div className="bg-white rounded-xl border p-5"><h4 className="font-semibold mb-1">业务数据：实例类型分布</h4><p className="text-xs text-gray-400 mb-4">当前已导入或映射的业务实例</p><BarList items={data.entity_types} empty="暂无业务实例数据" /></div>
      <div className="bg-white rounded-xl border p-5"><h4 className="font-semibold mb-1">本体结构：关系类型分布</h4><p className="text-xs text-gray-400 mb-4">实体之间的语义关系数量</p><BarList items={data.relation_types || []} empty="暂无关系数据" /></div>
    </section>

    <section className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <div className="bg-white rounded-xl border p-5"><div className="flex items-center gap-2 mb-4"><AlertTriangle size={17} className="text-rose-600" /><h4 className="font-semibold">风险中心</h4><span className="text-xs text-gray-400">自动识别</span></div>{data.risk_items.length ? <div className="divide-y max-h-80 overflow-auto">{data.risk_items.map((risk, index) => <div key={`${risk.title}-${index}`} className="py-3 flex items-start gap-3"><span className={`mt-1 w-2 h-2 rounded-full flex-shrink-0 ${risk.severity === 'high' ? 'bg-red-500' : 'bg-amber-500'}`} /><div className="min-w-0 flex-1"><p className="text-sm font-medium text-gray-800 truncate">{risk.title || '未命名记录'}</p><p className="text-xs text-gray-500 mt-1">{risk.reason} · {risk.type}</p></div></div>)}</div> : <p className="text-sm text-gray-400 py-5">暂未发现规则化风险记录</p>}</div>
      <div className="bg-white rounded-xl border p-5"><div className="flex items-center gap-2 mb-4"><Database size={17} className="text-blue-600" /><h4 className="font-semibold">数据来源与质量</h4></div><BarList items={data.sources} empty="暂无来源信息" /><div className="mt-5 pt-4 border-t text-xs text-gray-500">本体实体 {totals.ontology_entities ?? 0} 个 · 概念节点 {totals.concepts} 个 · 业务实例 {totals.rows} 条 · 业务类型 {totals.data_types ?? data.entity_types.length} 种</div></div>
    </section>
  </div>
}
