import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { BarChart3, ChevronRight, Database, ShieldAlert } from 'lucide-react'
import { ontologyApi } from '@/api/ontologies'

type OntologyItem = { id: string; name: string; domain: string; status: string; entity_count: number; logic_count: number; action_count: number }

const domainColors: Record<string, string> = {
  供应链: 'bg-blue-50 text-blue-700 border-blue-200', 财务: 'bg-amber-50 text-amber-700 border-amber-200', 法律: 'bg-violet-50 text-violet-700 border-violet-200',
  教育: 'bg-pink-50 text-pink-700 border-pink-200', 医疗: 'bg-emerald-50 text-emerald-700 border-emerald-200', 营销: 'bg-rose-50 text-rose-700 border-rose-200', HR: 'bg-indigo-50 text-indigo-700 border-indigo-200',
}

export default function AnalyticsHubPage() {
  const navigate = useNavigate()
  const { data, isLoading } = useQuery({ queryKey: ['analytics-hub-ontologies'], queryFn: () => ontologyApi.list({ page_size: 1000 }) as any })
  const items: OntologyItem[] = data?.items ?? []

  return <div className="space-y-6">
    <div className="flex items-start justify-between"><div><h2 className="text-xl font-semibold">分析看板</h2><p className="text-sm text-gray-500 mt-1">跨领域查看数据规模、业务分布、风险记录和数据来源质量</p></div><div className="flex items-center gap-2 text-sm text-gray-500"><BarChart3 size={18} /> {items.length} 个本体</div></div>
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div className="bg-white rounded-xl border p-4"><div className="flex justify-between text-sm text-gray-500"><span>本体领域</span><Database size={16} /></div><p className="text-2xl font-semibold mt-3">{new Set(items.map(item => item.domain)).size}</p></div>
      <div className="bg-white rounded-xl border p-4"><div className="flex justify-between text-sm text-gray-500"><span>实体总数</span><Database size={16} /></div><p className="text-2xl font-semibold mt-3">{items.reduce((sum, item) => sum + (item.entity_count || 0), 0).toLocaleString()}</p></div>
      <div className="bg-white rounded-xl border p-4"><div className="flex justify-between text-sm text-gray-500"><span>逻辑规则</span><ShieldAlert size={16} /></div><p className="text-2xl font-semibold mt-3">{items.reduce((sum, item) => sum + (item.logic_count || 0), 0).toLocaleString()}</p></div>
      <div className="bg-white rounded-xl border p-4"><div className="flex justify-between text-sm text-gray-500"><span>动作总数</span><BarChart3 size={16} /></div><p className="text-2xl font-semibold mt-3">{items.reduce((sum, item) => sum + (item.action_count || 0), 0).toLocaleString()}</p></div>
    </div>
    {isLoading ? <div className="py-12 text-center text-gray-400">正在加载领域数据…</div> : <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">{items.map(item => <button key={item.id} onClick={() => navigate(`/ontologies/${item.id}?tab=analytics`)} className="text-left bg-white rounded-xl border p-5 hover:border-gray-400 hover:shadow-sm transition-all"><div className="flex items-start justify-between gap-3"><div><span className={`inline-flex px-2 py-1 rounded-md border text-xs ${domainColors[item.domain] ?? 'bg-gray-50 text-gray-600 border-gray-200'}`}>{item.domain}</span><h3 className="font-semibold mt-3">{item.name}</h3></div><ChevronRight size={18} className="text-gray-400 mt-1" /></div><div className="flex gap-4 text-xs text-gray-500 mt-5"><span>实体 {item.entity_count ?? 0}</span><span>规则 {item.logic_count ?? 0}</span><span>动作 {item.action_count ?? 0}</span></div><p className="text-xs text-blue-600 mt-4">进入四大分析模块</p></button>)}</div>}
  </div>
}
