<template>
  <div class="tree-node">
    <div
      v-if="node.is_dir"
      class="tree-item dir"
      :class="{ expanded }"
      @click="toggleExpand"
    >
      <span class="expand-icon">{{ expanded ? '▼' : '▶' }}</span>
      <span class="node-icon">📁</span>
      <span class="node-name">{{ node.name }}</span>
    </div>
    <div
      v-else
      class="tree-item file"
      :class="{ selected: selectedPath === node.path }"
      @click="$emit('select', node.path)"
    >
      <span class="expand-icon placeholder"></span>
      <span class="node-icon">{{ fileIcon(node.language) }}</span>
      <span class="node-name">{{ node.name }}</span>
    </div>
    <div v-if="node.is_dir && expanded && node.children?.length" class="tree-children">
      <FileTreeNode
        v-for="child in sortedChildren"
        :key="child.path"
        :node="child"
        :selected-path="selectedPath"
        @select="$emit('select', $event)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface FileNode {
  name: string
  path: string
  is_dir: boolean
  children?: FileNode[]
  language?: string
  size?: number
}

const props = defineProps<{
  node: FileNode
  selectedPath: string
}>()

defineEmits<{
  (e: 'select', path: string): void
}>()

const expanded = ref(props.node.path === '' || props.node.path.split('/').length <= 2)

const sortedChildren = computed(() => {
  if (!props.node.children) return []
  return [...props.node.children].sort((a, b) => {
    // 目录优先
    if (a.is_dir !== b.is_dir) return a.is_dir ? -1 : 1
    // 按名称排序
    return a.name.toLowerCase().localeCompare(b.name.toLowerCase())
  })
})

function toggleExpand() {
  expanded.value = !expanded.value
}

function fileIcon(language?: string): string {
  const icons: Record<string, string> = {
    python: '🐍',
    java: '☕',
    javascript: '📜',
    typescript: '💠',
    vue: '💚',
    html: '🌐',
    css: '🎨',
    scss: '🎨',
    json: '📋',
    yaml: '⚙️',
    markdown: '📝',
    sql: '🗃️',
    shell: '💻',
    go: '🔵',
    rust: '🦀',
    c: '©️',
    cpp: '➕',
    ruby: '💎',
    php: '🐘',
    swift: '🍎',
    kotlin: '🟣',
  }
  return icons[language || ''] || '📄'
}
</script>

<style scoped>
.tree-node {
  user-select: none;
}

.tree-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}

.tree-item:hover {
  background: rgba(37, 99, 235, 0.08);
}

.tree-item.selected {
  background: rgba(37, 99, 235, 0.15);
  color: var(--primary-color);
}

.expand-icon {
  width: 12px;
  font-size: 10px;
  color: #64748b;
}

.expand-icon.placeholder {
  visibility: hidden;
}

.node-icon {
  font-size: 14px;
}

.node-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tree-children {
  padding-left: 16px;
}
</style>
