<script lang="ts">
  import { CircleAlert, CircleCheck, Info, X } from '@lucide/svelte'
  import { flip } from 'svelte/animate'
  import { fly } from 'svelte/transition'
  import { dismiss, notice } from '../notify.svelte'

  const ICONS = { success: CircleCheck, error: CircleAlert, info: Info }
</script>

<div class="toasts" aria-live="polite">
  {#each notice.toasts as toast (toast.id)}
    {@const Icon = ICONS[toast.tone]}
    <div
      class="toast {toast.tone}"
      role={toast.tone === 'error' ? 'alert' : 'status'}
      animate:flip={{ duration: 200 }}
      in:fly={{ y: 12, duration: 220 }}
      out:fly={{ x: 24, duration: 160 }}
    >
      <Icon size={18} />
      <p>{toast.text}</p>
      <button type="button" class="btn ghost icon small" aria-label="닫기" onclick={() => dismiss(toast.id)}>
        <X size={14} />
      </button>
    </div>
  {/each}
</div>

<style>
  .toasts {
    position: fixed;
    right: 20px;
    bottom: 20px;
    z-index: 50;
    display: grid;
    gap: 8px;
    width: min(380px, calc(100vw - 40px));
  }

  .toast {
    display: grid;
    grid-template-columns: auto 1fr auto;
    align-items: start;
    gap: 10px;
    padding: 12px 10px 12px 14px;
    border-radius: var(--radius-frame);
    background: var(--surface-2);
    border: 1px solid var(--line-strong);
    box-shadow: var(--shadow-pop);
  }

  .toast :global(svg:first-child) {
    margin-top: 1px;
  }

  .success :global(svg:first-child) {
    color: var(--success);
  }
  .error :global(svg:first-child) {
    color: var(--danger);
  }
  .info :global(svg:first-child) {
    color: var(--text-2);
  }

  p {
    font-size: var(--text-sm);
    white-space: pre-line;
    user-select: text;
  }

  .btn.icon.small {
    width: 24px;
    height: 24px;
  }
</style>
