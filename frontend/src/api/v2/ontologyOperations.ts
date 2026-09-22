import { apiClientV2 } from '@/api/client'

export type V2LogicRule = {
  id: string; name: string; logic_type: string; description?: string
  target_entity_type?: string; severity: string; enabled: boolean; status: string
  version?: number; expression?: Record<string, unknown>; created_at?: string
}

export type V2Action = {
  id: string; name: string; action_category: string; description?: string
  target_entity_type?: string; enabled: boolean; status: string; version?: number
  parameters?: unknown[]; effects?: unknown[]; permission_rules?: unknown[]
  created_at?: string
}

export const ontologyOperationsApi = {
  listLogic: (id: string) => apiClientV2.get<V2LogicRule[]>(`/ontologies/${id}/logic`),
  discoverLogic: (id: string) => apiClientV2.post(`/ontologies/${id}/logic/discover`, {}),
  publishLogic: (id: string) => apiClientV2.post(`/ontologies/${id}/logic/publish`, {}),
  reviewLogic: (id: string, ruleId: string, body: object) => apiClientV2.post(`/ontologies/${id}/logic/${ruleId}/review`, body),
  testLogic: (id: string, ruleId: string, body: object) => apiClientV2.post(`/ontologies/${id}/logic/${ruleId}/test`, body),
  listActions: (id: string) => apiClientV2.get<V2Action[]>(`/ontologies/${id}/actions`),
  discoverActions: (id: string) => apiClientV2.post(`/ontologies/${id}/actions/discover`, {}),
  publishActions: (id: string) => apiClientV2.post(`/ontologies/${id}/actions/publish`, {}),
  reviewAction: (id: string, actionId: string, body: object) => apiClientV2.post(`/ontologies/${id}/actions/${actionId}/review`, body),
  runAction: (id: string, actionId: string, body: object) => apiClientV2.post(`/ontologies/${id}/actions/${actionId}/run`, body),
  listRuns: (id: string) => apiClientV2.get(`/ontologies/${id}/action-runs`),
  listStateMachines: (id: string) => apiClientV2.get(`/ontologies/${id}/state-machines`),
  listMappings: (id: string) => apiClientV2.get(`/ontologies/${id}/mappings`),
  applyMapping: (id: string, mappingId: string) => apiClientV2.post(`/ontologies/${id}/mappings/${mappingId}/apply-from-dataset`, {}),
}
