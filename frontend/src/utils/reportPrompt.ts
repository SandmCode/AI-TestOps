import { ElMessageBox } from 'element-plus'

export async function promptAllureReport(taskLabel: string): Promise<boolean> {
  try {
    await ElMessageBox.confirm(
      `${taskLabel}已完成。是否生成 Allure 测试报告？\n报告将保存到「测试报告」，可随时打开查看。`,
      '生成测试报告',
      {
        confirmButtonText: '生成 Allure 报告',
        cancelButtonText: '暂不生成',
        type: 'info',
      },
    )
    return true
  } catch {
    return false
  }
}

export function openReportUrl(url: string) {
  if (!url) return
  window.open(url, '_blank')
}
