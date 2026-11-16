/** Small drawings for empty pages (P19 of the polish review), in the stamp's colours: what will be here. */
export function EmptyArt({ kind }: { kind: 'saved' | 'follow' }) {
  return (
    <svg aria-hidden="true" width="96" height="72" viewBox="0 0 96 72" className="text-stamp">
      <rect x="22" y="8" width="48" height="58" rx="6" className="fill-wash" />
      <path d="M31 24h28M31 33h22M31 42h26M31 51h16" stroke="currentColor" strokeWidth="3" strokeLinecap="round" opacity="0.4" />
      {kind === 'saved' ? (
        <path d="M58 2h16v30l-8-6-8 6z" fill="currentColor" />
      ) : (
        <>
          <circle cx="70" cy="50" r="15" className="fill-sheet" stroke="currentColor" strokeWidth="3" />
          <path d="M64 54v-6a6 6 0 0 1 12 0v6l2 2H62zM68 59h4" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
        </>
      )}
    </svg>
  );
}
