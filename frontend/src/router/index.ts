import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '@/layouts/MainLayout.vue'
import ModuleLayout from '@/layouts/ModuleLayout.vue'
import { APP_TITLE } from '@/config/app'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: MainLayout,
      redirect: '/home',
      children: [
        { path: 'home', name: 'Home', component: () => import('@/views/Home.vue'), meta: { title: '首页' } },
        { path: 'projects', name: 'Projects', component: () => import('@/views/Projects.vue'), meta: { title: '项目管理' } },
        { path: 'ai-config', redirect: '/llm-config/provider' },

        // 兼容旧路由
        { path: 'documents', redirect: '/requirement-center/documents' },
        { path: 'documents/:id/preview', name: 'DocumentPreview', component: () => import('@/views/DocumentPreview.vue'), meta: { title: '文档预览' } },
        { path: 'test-cases', redirect: '/test-case-factory/manage' },

        // 1️⃣ 需求中心
        {
          path: 'requirement-center',
          component: ModuleLayout,
          meta: { module: 'requirement-center' },
          redirect: '/requirement-center/documents',
          children: [
            { path: 'documents', component: () => import('@/views/Documents.vue'), meta: { title: '需求文档管理', module: 'requirement-center' } },
            { path: 'parse', component: () => import('@/views/requirement/Parse.vue'), meta: { title: '需求解析', module: 'requirement-center' } },
            { path: 'test-points', component: () => import('@/views/requirement/TestPointTree.vue'), meta: { title: '测试点树', module: 'requirement-center' } },
            { path: 'structure', redirect: '/requirement-center/test-points' },
          ],
        },

        // 兼容旧路由：测试设计已合并到测试用例
        { path: 'test-design', redirect: '/test-case-factory/manage' },
        { path: 'test-design/:pathMatch(.*)*', redirect: '/test-case-factory/manage' },

        // 2️⃣ 测试用例
        {
          path: 'test-case-factory',
          component: ModuleLayout,
          meta: { module: 'test-case-factory' },
          redirect: '/test-case-factory/manage',
          children: [
            { path: 'manage', component: () => import('@/views/TestCases.vue'), meta: { title: '用例管理', module: 'test-case-factory' } },
            { path: 'orchestration', redirect: '/test-case-factory/manage' },
            { path: 'templates', redirect: '/test-case-factory/manage' },
            { path: 'convert', component: () => import('@/views/case-factory/Convert.vue'), meta: { title: '用例转换', module: 'test-case-factory' } },
          ],
        },

        // 4️⃣ 接口测试
        {
          path: 'test-execution',
          component: ModuleLayout,
          meta: { module: 'test-execution' },
          redirect: '/test-execution/doc-parse',
          children: [
            { path: 'doc-parse', component: () => import('@/views/api-test/DocParse.vue'), meta: { title: '接口文档解析', module: 'test-execution' } },
            { path: 'automation', component: () => import('@/views/api-test/Automation.vue'), meta: { title: '接口自动化', module: 'test-execution' } },
            { path: 'security', component: () => import('@/views/api-test/SecurityScan.vue'), meta: { title: '接口安全扫描', module: 'test-execution' } },
            { path: 'stress', component: () => import('@/views/api-test/StressTest.vue'), meta: { title: '接口压测', module: 'test-execution' } },
            { path: 'runner', redirect: '/test-execution/automation' },
            { path: 'batch', redirect: '/test-execution/automation' },
            { path: 'analysis', redirect: '/test-execution/automation' },
          ],
        },

        { path: 'api-test', redirect: '/test-execution/doc-parse' },
        { path: 'mock-data', name: 'MockData', component: () => import('@/views/tools/MockData.vue'), meta: { title: '假数据生成' } },
        { path: 'json-tool', name: 'JsonTool', component: () => import('@/views/tools/JsonTool.vue'), meta: { title: 'JSON工具' } },
        { path: 'encode-tool', name: 'EncodeTool', component: () => import('@/views/tools/EncodeTool.vue'), meta: { title: '编码转换' } },
        { path: 'stress-tool', redirect: '/test-execution/stress' },
        { path: 'contract-test', name: 'ContractTest', component: () => import('@/views/ai/ContractTest.vue'), meta: { title: '契约测试' } },
        { path: 'coverage', name: 'Coverage', component: () => import('@/views/ai/CoverageAnalysis.vue'), meta: { title: '覆盖率分析' } },
        { path: 'log-analysis', name: 'LogAnalysis', component: () => import('@/views/ai/LogAnalysis.vue'), meta: { title: '日志分析' } },
        {
          path: 'test-reports-center',
          component: ModuleLayout,
          meta: { module: 'test-reports-center' },
          redirect: '/test-reports-center/list',
          children: [
            {
              path: 'list',
              component: () => import('@/views/test-reports/TestReports.vue'),
              meta: { title: '测试报告', module: 'test-reports-center' },
            },
          ],
        },

        { path: 'test-reports', redirect: '/test-reports-center/list' },

        // 系统管理 · 大模型配置
        {
          path: 'llm-config',
          component: ModuleLayout,
          meta: { module: 'llm-config' },
          redirect: '/llm-config/provider',
          children: [
            { path: 'provider', component: () => import('@/views/llm-config/ProviderConfig.vue'), meta: { title: 'AI 配置', module: 'llm-config' } },
            { path: 'skills', component: () => import('@/views/llm-config/SkillsConfig.vue'), meta: { title: 'Skills 配置', module: 'llm-config' } },
            { path: 'system', component: () => import('@/views/llm-config/SystemSettings.vue'), meta: { title: '系统设置', module: 'llm-config' } },
          ],
        },
      ],
    },
  ],
})

router.afterEach((to) => {
  const pageTitle = to.meta.title as string | undefined
  document.title = pageTitle ? `${pageTitle} - ${APP_TITLE}` : APP_TITLE
})

export default router
