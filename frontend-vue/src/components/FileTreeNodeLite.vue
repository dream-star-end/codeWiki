<template>
  <div class="tree-node">
    <div
      v-if="node.is_dir"
      class="flex items-center gap-1.5 px-2 py-1 rounded cursor-pointer hover:bg-[var(--accent-primary)]/10 transition-colors text-sm"
      @click="toggleExpand"
    >
      <span class="w-3 text-xs text-[var(--muted)]">{{ expanded ? '▼' : '▶' }}</span>
      <span>📁</span>
      <span class="truncate text-[var(--foreground)]">{{ node.name }}</span>
    </div>
    <div
      v-else
      class="flex items-center gap-1.5 px-2 py-1 rounded cursor-pointer hover:bg-[var(--accent-primary)]/10 transition-colors text-sm"
      :class="{ 'bg-[var(--accent-primary)]/15 text-[var(--accent-primary)]': selectedPath === node.path }"
      @click="$emit('select', node.path)"
    >
      <span class="w-3"></span>
      <span>{{ fileIcon(node.language) }}</span>
      <span class="truncate" :class="selectedPath === node.path ? 'text-[var(--accent-primary)]' : 'text-[var(--foreground)]'">{{ node.name }}</span>
    </div>
    <div v-if="node.is_dir && expanded && node.children?.length" class="pl-3">
      <FileTreeNodeLite
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
    if (a.is_dir !== b.is_dir) return a.is_dir ? -1 : 1
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
    json: '📋',
    yaml: '⚙️',
    markdown: '📝',
    sql: '🗃️',
    shell: '💻',
    go: '🔵',
    rust: '🦀',
  }
  return icons[language || ''] || '📄'
}
</script>
