import React, { useState, lazy, Suspense } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { ontologyApi } from '@/api/ontologies'
import StatusBadge from '@/components/StatusBadge'
import InfoTab from './tabs/InfoTab'
import FilesTab from './tabs/FilesTab'
import EntitiesTab from './tabs/EntitiesTab'
import LogicTab from './tabs/LogicTab'
import ActionsTab from './tabs/ActionsTab'
import AuditTab from './tabs/AuditTab'
import CuratedDatasetsTab from './tabs/CuratedDatasetsTab'
import AnalyticsTab from './tabs/AnalyticsTab'
import OperationsTab from './tabs/OperationsTab'
import { Activity, ArrowRight, Boxes, GitBranch, ListChecks, Network, Sparkles } from 'lucide-react'


const GraphTab = lazy(() => import('./tabs/GraphTabV2'))

type Tab = 'info' | 'analytics' | 'operations' | 'graph' | 'entities' | 'logic' | 'actions' | 'files' | 'extract' |  'audit' | 'curated'

function OntologyCommandCenter({ ontologyId, ontology, onOpen }: { ontologyId: string; ontology: any; onOpen: (tab: Tab) => void }) {
  const entities = useQuery({ queryKey: ['entities', ontologyId], queryFn: () => ontologyApi.listEntities(ontologyId) as any })
  const logic = useQuery({ queryKey: ['logic', ontologyId], queryFn: () => ontologyApi.listLogic(ontologyId) as any })
  const actions = useQuery({ queryKey: ['actions', ontologyId], queryFn: () => ontologyApi.listActions(ontologyId) as any })
  const graph = useQuery({ queryKey: ['graph', ontologyId], queryFn: () => ontologyApi.getGraph(ontologyId) as any })
  const cards = [
    { label: '实体', value: entities.data?.length ?? 0, icon: Boxes, tab: 'entities' as Tab, iconClass: 'text-blue-300' },
    { label: '关系', value: graph.data?.edges?.length ?? 0, icon: Network, tab: 'graph' as Tab, iconClass: 'text-emerald-300' },
    { label: '逻辑规则', value: logic.data?.length ?? 0, icon: GitBranch, tab: 'logic' as Tab, iconClass: 'text-violet-300' },
    { label: '业务动作', value: actions.data?.length ?? 0, icon: ListChecks, tab: 'actions' as Tab, iconClass: 'text-amber-300' },
  ]
  const total = cards.reduce((sum, card) => sum + card.value, 0)
  return (
    <section className="mb-6 rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950 p-5 text-white shadow-sm">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="mb-2 flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-indigo-200"><Sparkles size={14} /> Ontology command center</div>
          <h3 className="text-lg font-semibold">{ontology.name} 的知识资产总览</h3>
          <p className="mt-1 max-w-2xl text-sm text-slate-300">从实体、关系到规则和动作，快速查看这个本体当前已经沉淀的可用知识。</p>
        </div>
        <button onClick={() => onOpen('analytics')} className="inline-flex items-center gap-1.5 self-start rounded-lg border border-white/20 bg-white/10 px-3 py-2 text-sm hover:bg-white/20"><Activity size={15} /> 查看分析 <ArrowRight size={14} /></button>
      </div>
      <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {cards.map(({ label, value, icon: Icon, tab, iconClass }) => (
          <button key={label} onClick={() => onOpen(tab)} className="group rounded-xl border border-white/10 bg-white/[0.08] p-4 text-left transition hover:bg-white/[0.15]">
            <div className="flex items-center justify-between text-slate-300"><span className="text-sm">{label}</span><Icon size={18} className={iconClass} /></div>
            <div className="mt-2 text-3xl font-semibold">{value}</div>
            <div className="mt-1 text-xs text-slate-400">点击进入明细 <ArrowRight size={12} className="inline transition group-hover:translate-x-1" /></div>
          </button>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-white/10 pt-3 text-xs text-slate-300">
        <span>版本 {ontology.version}</span><span>领域 {ontology.domain}</span><span>共 {total} 项结构化资产</span>
        {graph.data && <span className="text-emerald-300">图谱已加载</span>}
      </div>
    </section>
  )
}

class GraphErrorBoundary extends React.Component<
  { children: React.ReactNode; fallbackLabel?: string },
  { hasError: boolean; error: string }
> {
  constructor(props: any) {
    super(props)
    this.state = { hasError: false, error: '' }
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error: error.message }
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="bg-red-50 border border-red-200 rounded-lg p-8 text-center">
          <p className="text-red-600 font-medium mb-2">{this.props.fallbackLabel || '图表加载失败'}</p>
          <p className="text-red-400 text-sm font-mono">{this.state.error}</p>
          <button
            onClick={() => this.setState({ hasError: false, error: '' })}
            className="mt-4 px-3 py-1.5 text-sm border border-red-300 text-red-500 rounded-lg hover:bg-red-100">
            重试
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

export default function OntologyDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [searchParams] = useSearchParams()
  const initialTab = (searchParams.get('tab') as Tab) || 'info'
  const [activeTab, setActiveTab] = useState<Tab>(initialTab)

  const { data: ontology, isLoading } = useQuery({
    queryKey: ['ontology', id],
    queryFn: () => ontologyApi.get(id!) as any,
    enabled: !!id,
  })

  if (isLoading) return <div className="p-6 text-gray-400">{t('common.loading')}</div>
  if (!ontology) return <div className="p-6 text-red-500">Ontology not found</div>

  const isPipelineMode = (ontology as any).build_mode === 'pipeline_mapping'

  const tabs: { key: Tab; label: string }[] = [
    { key: 'info', label: t('ontology.tabs.info') },
    { key: 'analytics', label: '数据分析' },
    { key: 'operations', label: '运行中心' },
    { key: 'graph', label: t('ontology.tabs.graph') },
    { key: 'entities', label: t('ontology.tabs.entities') },
    { key: 'logic', label: t('ontology.tabs.logic') },
    { key: 'actions', label: t('ontology.tabs.actions') },
    { key: 'audit', label: t('ontology.tabs.audit') },
    isPipelineMode
      ? { key: 'curated', label: 'Curated 数据集' }
      : { key: 'files', label: t('ontology.tabs.files') },
  ]

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <button onClick={() => navigate('/ontologies')} className="text-gray-500 hover:text-black text-sm">{t('ontology.back')}</button>
        <h2 className="text-xl font-semibold">{ontology.name}</h2>
        <StatusBadge status={ontology.status} />
        <span className="text-gray-400 text-sm">{ontology.domain} · {ontology.version}</span>
      </div>

      <div className="border-b mb-6">
        <div className="flex gap-1">
          {tabs.map(tab => (
            <button key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                  ? 'border-black text-black'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}>
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <OntologyCommandCenter ontologyId={id!} ontology={ontology} onOpen={setActiveTab} />

      <div>
        {activeTab === 'info' && <InfoTab ontology={ontology} />}
        {activeTab === 'analytics' && <AnalyticsTab ontologyId={id!} />}
        {activeTab === 'operations' && <OperationsTab ontologyId={id!} />}
        {activeTab === 'files' && <FilesTab ontologyId={id!} />}
        {activeTab === 'curated' && <CuratedDatasetsTab ontologyId={id!} />}
        {activeTab === 'graph' && (
          <GraphErrorBoundary fallbackLabel="知识图谱渲染失败">
            <Suspense fallback={<div className="text-gray-400 py-8 text-center">{t('common.loading')}</div>}>
              <GraphTab ontologyId={id!} />
            </Suspense>
          </GraphErrorBoundary>
        )}
        {activeTab === 'entities' && <EntitiesTab ontologyId={id!} />}
        {activeTab === 'logic' && <LogicTab ontologyId={id!} />}
        {activeTab === 'actions' && <ActionsTab ontologyId={id!} />}
        {activeTab === 'audit' && <AuditTab ontologyId={id!} />}
      </div>
    </div>
  )
}
