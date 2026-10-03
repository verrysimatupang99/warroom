import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import ProposalCard from './ProposalCard.svelte';
import type { Proposal } from '$lib/api/types';

const usulan: Proposal = {
	id: 12,
	parameter: 'agent.threshold',
	dari: 0.82,
	ke: 0.84,
	alasan: 'bukti bukan split beku',
	bukti: { n: 3977, win: 3107 },
	gate: 'insufficient',
	status: 'ditolak',
	ditolak_karena: 'bukti bukan split beku menurut ADR-003',
	diputuskan_oleh: null,
	diterapkan_pada: null,
	config_hash: null,
	dibuat: '2026-10-03T06:52:32Z'
};

describe('ProposalCard', () => {
	it('menampilkan parameter, dari→ke, status, dan alasan penolakan', () => {
		render(ProposalCard, { props: { proposals: [usulan] } });
		const t = screen.getByTestId('proposal-card').textContent ?? '';
		expect(t).toContain('agent.threshold');
		expect(t).toContain('0,82');
		expect(t).toContain('0,84');
		expect(t).toContain('ditolak');
		expect(t).toContain('bukti bukan split beku');
		expect(t).toContain('#12');
	});

	it('viewer tidak melihat tombol aksi; owner melihat tombol terapkan', () => {
		const { unmount } = render(ProposalCard, {
			props: { proposals: [usulan], peran: 'viewer', onexec: () => {} }
		});
		expect(screen.queryByText('terapkan')).toBeNull();
		unmount();

		render(ProposalCard, { props: { proposals: [usulan], peran: 'owner', onexec: () => {} } });
		expect(screen.queryByText('terapkan')).not.toBeNull();
	});

	it('proposal diterapkan → tombol rollback (bukan terapkan)', () => {
		render(ProposalCard, {
			props: {
				proposals: [{ ...usulan, status: 'diterapkan', diputuskan_oleh: 'owner' }],
				peran: 'owner',
				onexec: () => {}
			}
		});
		expect(screen.queryByText('rollback')).not.toBeNull();
		expect(screen.queryByText('terapkan')).toBeNull();
	});

	it('daftar kosong → EmptyState jujur, bukan kartu karangan', () => {
		render(ProposalCard, { props: { proposals: [] } });
		expect(screen.getByTestId('empty-state')).toBeTruthy();
	});
});
