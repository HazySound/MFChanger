<script lang="ts">
  import { fade } from 'svelte/transition'

  interface Props {
    title: string
    label: string
    /** 0~1 */
    fraction: number
    note: string
  }

  let { title, label, fraction, note }: Props = $props()
</script>

<div
  class="overlay"
  role="dialog"
  aria-modal="true"
  aria-labelledby="progress-title"
  transition:fade={{ duration: 160 }}
>
  <div class="box">
    <h2 id="progress-title">{title}</h2>
    <p class="muted">{label} ({Math.round(fraction * 100)}%)</p>
    <div
      class="bar"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(fraction * 100)}
    >
      <span style:transform="scaleX({fraction})"></span>
    </div>
    <p class="faint">{note}</p>
  </div>
</div>

<style>
  .overlay {
    position: fixed;
    inset: 0;
    z-index: 60;
    display: grid;
    place-items: center;
    background: var(--bg);
  }

  .box {
    display: grid;
    justify-items: center;
    gap: 10px;
    width: min(440px, 80vw);
    text-align: center;
  }

  h2 {
    font-size: var(--text-xl);
  }

  .bar {
    width: 100%;
    height: 8px;
    margin-top: 8px;
    border-radius: 999px;
    background: var(--surface-3);
    overflow: hidden;
  }

  .bar span {
    display: block;
    height: 100%;
    background: var(--gold);
    transform-origin: left;
    transition: transform 0.3s var(--ease-out);
  }
</style>
