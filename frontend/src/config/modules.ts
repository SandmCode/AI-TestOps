export interface ModuleTab {
  path: string
  title: string
  icon: string
}

export const moduleTabs: Record<string, ModuleTab[]> = {
  'requirement-center': [
    { path: '/requirement-center/documents', title: '需求文档', icon: 'Document' },
    { path: '/requirement-center/parse', title: '需求解析', icon: 'MagicStick' },
    { path: '/requirement-center/test-points', title: '测试点树', icon: 'Share' },
  ],
  'test-case-factory': [
    { path: '/test-case-factory/manage', title: '用例管理', icon: 'List' },
    { path: '/test-case-factory/convert', title: '格式转换', icon: 'Switch' },
  ],
  'test-execution': [
    { path: '/test-execution/doc-parse', title: '接口文档解析', icon: 'Document' },
    { path: '/test-execution/automation', title: '接口自动化', icon: 'Connection' },
    { path: '/test-execution/security', title: '接口安全扫描', icon: 'Lock' },
    { path: '/test-execution/stress', title: '接口压测', icon: 'Lightning' },
  ],
  'test-reports-center': [
    { path: '/test-reports-center/list', title: '报告列表', icon: 'DocumentCopy' },
  ],
  'llm-config': [
    { path: '/llm-config/provider', title: 'AI 配置', icon: 'Setting' },
    { path: '/llm-config/skills', title: 'Skills 配置', icon: 'Notebook' },
    { path: '/llm-config/system', title: '系统设置', icon: 'Tools' },
  ],
}

export const moduleTitles: Record<string, string> = {
  'requirement-center': '需求中心',
  'test-case-factory': '测试用例',
  'test-execution': '接口测试',
  'test-reports-center': '测试报告',
  'llm-config': '大模型配置',
}
