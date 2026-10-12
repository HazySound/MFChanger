<script lang="ts">
  interface Props {
    checked: boolean
    label: string
    onChange: (checked: boolean) => void
  }

  let { checked, label, onChange }: Props = $props()
</script>

<label class="switch">
  <input type="checkbox" role="switch" {checked} onchange={(e) => onChange(e.currentTarget.checked)} />
  <span class="track" aria-hidden="true"></span>
  <span>{label}</span>
</label>

<style>
  .switch {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
  }

  input {
    position: absolute;
    opacity: 0;
    pointer-events: none;
  }

  .track {
    position: relative;
    width: 36px;
    height: 20px;
    border-radius: 999px;
    background: var(--surface-3);
    border: 1px solid var(--line-strong);
    transition: background 0.2s;
  }

  .track::after {
    content: '';
    position: absolute;
    top: 2px;
    left: 2px;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: var(--text-2);
    transition:
      transform 0.2s var(--ease-out),
      background 0.2s;
  }

  input:checked + .track {
    background: var(--gold);
    border-color: var(--gold);
  }

  input:checked + .track::after {
    transform: translateX(16px);
    background: var(--gold-ink);
  }

  input:focus-visible + .track {
    outline: 2px solid var(--gold);
    outline-offset: 2px;
  }
</style>
