<script lang="ts">
  import { fade, scale } from 'svelte/transition'
  import { notice } from '../notify.svelte'

  let confirmButton = $state<HTMLButtonElement>()

  $effect(() => {
    if (notice.confirm) confirmButton?.focus()
  })

  function onKeydown(event: KeyboardEvent) {
    if (notice.confirm && event.key === 'Escape') notice.confirm.resolve(false)
  }
</script>

<svelte:window onkeydown={onKeydown} />

{#if notice.confirm}
  {@const request = notice.confirm}
  <div class="backdrop" transition:fade={{ duration: 140 }}>
    <div
      class="dialog"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="confirm-title"
      transition:scale={{ start: 0.96, duration: 160 }}
    >
      <h2 id="confirm-title">{request.title}</h2>
      <p>{request.message}</p>
      <div class="actions">
        <button type="button" class="btn" onclick={() => request.resolve(false)}>취소</button>
        <button
          type="button"
          class="btn {request.danger ? 'danger' : 'primary'}"
          bind:this={confirmButton}
          onclick={() => request.resolve(true)}
        >
          {request.confirmLabel}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 40;
    display: grid;
    place-items: center;
    padding: 24px;
    background: var(--scrim);
  }

  .dialog {
    display: grid;
    gap: 12px;
    width: min(440px, 100%);
    padding: 22px 22px 18px;
    border-radius: var(--radius-panel);
    background: var(--surface);
    border: 1px solid var(--line-strong);
    box-shadow: var(--shadow-pop);
  }

  p {
    color: var(--text-2);
    font-size: var(--text-md);
    white-space: pre-line;
    user-select: text;
  }

  .actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 6px;
  }
</style>
