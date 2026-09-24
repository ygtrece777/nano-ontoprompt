export type OntologyStatus = 'draft' | 'creating' | 'created' | 'archived'

export interface OntologyListItem {
  id: string
  name: string
  domain: string
  version: string
  status: OntologyStatus
  build_mode?: string
  entity_count: number
  relation_count: number
  created_by: string
  created_at: string
  updated_at: string
}

export interface OntologyDetail extends OntologyListItem {
  description?: string
  build_mode?: string
  created_at: string
}

export interface Entity {
  id: string
  ontology_id: string
  name_cn: string
  name_en?: string
  name_abbr?: string
  snomed_id?: string
  canonical_id?: string
  type?: string
  description?: string
  properties: Record<string, unknown>
  confidence: number
  version: string
  created_at: string
  updated_at: string
}

export interface LogicRule {
  id: string
  ontology_id: string
  name_cn: string
  name_en?: string
  description?: string
  formula?: string
  confidence: number
  version: string
  enabled?: boolean
  status?: string
  linked_entities: string[]
  created_at: string
  updated_at: string
}

export interface Action {
  id: string
  ontology_id: string
  name_cn: string
  name_en?: string
  description?: string
  execution_rule?: string
  function_code?: string
  linked_entities: string[]
  linked_logic_ids: string[]
  confidence: number
  version: string
  status?: string
  enabled?: boolean
  created_at: string
  updated_at: string
}

export interface UploadedFile {
  id: string
  ontology_id: string
  filename: string
  file_size: number
  mime_type?: string
  created_at: string
}

export interface Prompt {
  id: string
  name: string
  domain: string
  content: string
  version: string
  created_by: string
  created_at: string
  updated_at: string
}

export interface ModelConfig {
  id: string
  name: string
  config_type: 'llm' | 'ocr' | 'other'
  provider: string
  api_base?: string
  models: string[]
  options?: Record<string, unknown>
  created_by: string
  created_at: string
  updated_at: string
}

export const DOMAINS = [
  '供应链', '采购', '财务', '医疗', '金融', '法律', '教育', '科技',
  '制造', '能源', 'HR', '营销', 'IT服务管理', '零售电商', '网络安全',
  '房地产物业', '项目研发', '保险理赔', '政务服务', '科研知识', '其他',
]

export const DOMAIN_PRESETS: Record<string, { description: string; entities: string[]; relations: string[] }> = {
  '制造': { description: '生产、设备、工单与质量控制', entities: ['工厂', '产线', '设备', '工单', '物料', '批次', '质检', '缺陷'], relations: ['生产', '使用物料', '产生批次', '通过质检', '触发维修'] },
  '能源': { description: '能源资产、计量、消耗与告警', entities: ['电站', '设备', '线路', '仪表', '能源消耗', '告警', '维修任务'], relations: ['包含设备', '监测', '产生告警', '触发维修'] },
  'IT服务管理': { description: '用户、资产、服务、工单与 SLA', entities: ['用户', '部门', '设备', '应用', '服务', '工单', '故障', 'SLA'], relations: ['提交工单', '影响服务', '分配给', '违反SLA'] },
  '零售电商': { description: '客户、商品、订单、库存与营销', entities: ['客户', '商品', '订单', '购物车', '优惠券', '库存', '门店', '供应商'], relations: ['购买', '包含商品', '使用优惠券', '库存于'] },
  '网络安全': { description: '资产、漏洞、告警、攻击与处置', entities: ['用户', '资产', '账号', '漏洞', '攻击', '告警', '安全事件', '处置任务'], relations: ['拥有账号', '存在漏洞', '触发告警', '关联攻击', '触发处置'] },
  '房地产物业': { description: '项目、房屋、业主、租约与维修', entities: ['项目', '楼栋', '房屋', '业主', '租户', '合同', '维修工单', '缴费'], relations: ['包含房屋', '拥有', '租赁', '产生工单'] },
  '项目研发': { description: '项目、需求、任务、版本与缺陷', entities: ['项目', '需求', '任务', '人员', '里程碑', '版本', '缺陷', '风险'], relations: ['包含需求', '分配任务', '属于里程碑', '修复缺陷'] },
  '保险理赔': { description: '保单、客户、事故、案件与赔付', entities: ['客户', '保单', '保险标的', '事故', '理赔案件', '材料', '核损', '赔付'], relations: ['持有保单', '发生事故', '提交理赔', '需要材料', '产生赔付'] },
  '政务服务': { description: '事项、申请人、材料、审批与办理', entities: ['申请人', '政务事项', '申请', '材料', '部门', '审批', '办理结果'], relations: ['申请事项', '提交材料', '受理部门', '经过审批', '产生结果'] },
  '科研知识': { description: '论文、作者、机构、课题与实验结果', entities: ['论文', '作者', '机构', '课题', '实验', '数据集', '方法', '结论'], relations: ['作者发表', '机构隶属', '研究课题', '使用方法', '得出结论'] },
}
