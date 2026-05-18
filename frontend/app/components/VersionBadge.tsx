export function VersionBadge({ version }: { version: number }) {
  if (version <= 1) return null
  return (
    <span className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold bg-indigo-100 text-indigo-700 border border-indigo-300">
      v{version}
    </span>
  )
}
