/**
 * 代码面板高度拖拽 composable
 */
import { computed, ref } from 'vue'

const MIN_PANEL_HEIGHT = 120
const MAX_PANEL_RATIO = 0.5

export function useCodePanelResize() {
  const codePanelRef = ref<HTMLElement>()
  const isResizing = ref(false)
  const codePanelHeight = ref<number | null>(null) // null = 自适应
  const START_RESIZE_Y = ref(0)
  const START_PANEL_HEIGHT = ref(0)

  /**
   * 动态样式:
   * - 默认(null):自适应内容高度,max-height 50%
   * - 拖拽后(有固定值):固定高度 + flex:none(覆盖 CSS flex:0 0 auto)
   */
  const codePanelStyle = computed(() => {
    if (codePanelHeight.value !== null) {
      return { height: codePanelHeight.value! + 'px', flex: 'none' }
    }
    return {}
  })

  function startResize(e: MouseEvent) {
    isResizing.value = true
    START_RESIZE_Y.value = e.clientY
    if (codePanelRef.value) {
      START_PANEL_HEIGHT.value = codePanelRef.value.getBoundingClientRect().height
    }
    document.addEventListener('mousemove', doResize)
    document.addEventListener('mouseup', stopResize)
    document.body.style.cursor = 'row-resize'
    document.body.style.userSelect = 'none'
  }

  function doResize(e: MouseEvent) {
    if (!isResizing.value || !codePanelRef.value) return
    const chatSection = codePanelRef.value.parentElement
    if (!chatSection) return

    const delta = START_RESIZE_Y.value - e.clientY
    const sectionHeight = chatSection.getBoundingClientRect().height
    const maxHeight = sectionHeight * MAX_PANEL_RATIO
    const minHeight = MIN_PANEL_HEIGHT

    let newHeight = START_PANEL_HEIGHT.value + delta
    newHeight = Math.max(minHeight, Math.min(maxHeight, newHeight))
    codePanelHeight.value = Math.round(newHeight)
  }

  function stopResize() {
    isResizing.value = false
    document.removeEventListener('mousemove', doResize)
    document.removeEventListener('mouseup', stopResize)
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }

  return {
    codePanelRef,
    codePanelHeight,
    codePanelStyle,
    isResizing,
    startResize,
  }
}
