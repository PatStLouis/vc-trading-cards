import { describe, it, expect } from 'vitest';
import { activeCard } from '$lib/stores/activeCard';

describe('activeCard store', () => {
  it('exports a writable store', () => {
    expect(activeCard).toBeDefined();
    expect(typeof activeCard.set).toBe('function');
    expect(typeof activeCard.subscribe).toBe('function');
  });

  it('initial value is null', () => {
    let value: unknown;
    activeCard.subscribe((v) => { value = v; })();
    expect(value).toBe(null);
  });
});
