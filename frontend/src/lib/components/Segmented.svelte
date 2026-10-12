<script lang="ts" generics="T extends string">
  interface Props {
    options: { value: T; label: string }[]
    value: T
    onChange: (value: T) => void
    label: string
  }

  let { options, value, onChange, label }: Props = $props()
</script>

<div class="segmented" role="radiogroup" aria-label={label}>
  {#each options as option (option.value)}
    <button
      type="button"
      role="radio"
      aria-checked={value === option.value}
      class:active={value === option.value}
      onclick={() => onChange(option.value)}
    >
      {option.label}
    </button>
  {/each}
</div>

<style>
  .segmented {
    display: inline-flex;
    padding: 3px;
    gap: 2px;
    border-radius: var(--radius-control);
    background: var(--surface-2);
    border: 1px solid var(--line);
  }

  button {
    height: 28px;
    padding: 0 12px;
    border: 0;
    border-radius: 6px;
    background: transparent;
    color: var(--text-2);
    font-size: var(--text-sm);
    font-weight: 600;
    white-space: nowrap;
    cursor: pointer;
    transition:
      background 0.15s,
      color 0.15s;
  }

  button:hover:not(.active) {
    color: var(--text);
  }

  button.active {
    background: var(--surface-3);
    color: var(--text);
    box-shadow: inset 0 0 0 1px var(--line-strong);
  }
</style>
