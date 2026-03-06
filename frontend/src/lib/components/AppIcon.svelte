<script lang="ts">
  /** Size variant for the app icon. */
  type Size = 'sm' | 'md' | 'lg';
  let { size = 'md', class: className = '' }: { size?: Size; class?: string } = $props();
  import { APP_ICON_URL } from '$lib/app-icon';
  const sizeClasses: Record<Size, string> = {
    sm: 'w-6 h-6',
    md: 'w-8 h-8',
    lg: 'w-10 h-10',
  };
</script>

<img
  src={APP_ICON_URL}
  alt="Tritone Cards"
  class="shrink-0 rounded-lg object-contain {sizeClasses[size]} {className}"
  width={size === 'sm' ? 24 : size === 'md' ? 32 : 40}
  height={size === 'sm' ? 24 : size === 'md' ? 32 : 40}
/>
