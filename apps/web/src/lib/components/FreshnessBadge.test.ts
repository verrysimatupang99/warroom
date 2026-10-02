import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import FreshnessBadge from './FreshnessBadge.svelte';

describe('FreshnessBadge', () => {
	it('menampilkan `basi` + umur menit', () => {
		render(FreshnessBadge, { props: { status: 'basi', age_s: 600, ttl_s: 1800, source: 'state/x' } });
		const el = screen.getByTestId('freshness');
		expect(el.textContent).toContain('basi 10m');
		expect(el.getAttribute('data-nada')).toBe('basi');
		expect(el.getAttribute('title')).toContain('state/x');
	});

	it('menampilkan `segar` + umur detik', () => {
		render(FreshnessBadge, { props: { status: 'segar', age_s: 45 } });
		const el = screen.getByTestId('freshness');
		expect(el.textContent).toContain('segar 45s');
		expect(el.getAttribute('data-nada')).toBe('segar');
	});

	it('tanpa status → n/a (bukan 0)', () => {
		render(FreshnessBadge, { props: {} });
		const el = screen.getByTestId('freshness');
		expect(el.textContent).toContain('n/a');
		expect(el.getAttribute('data-nada')).toBe('n/a');
	});

	it('cache menimpa status sumber', () => {
		render(FreshnessBadge, { props: { status: 'segar', age_s: 120, cache: true } });
		const el = screen.getByTestId('freshness');
		expect(el.textContent).toContain('cache 2m');
		expect(el.getAttribute('data-nada')).toBe('cache');
	});
});