import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-rule">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-8 text-sm text-ink-2 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <p>AsVoted runs on GenLayer Studio Dev. Every figure on this site is read from the contracts.</p>
        <p className="flex gap-4">
          <Link href="/verify" className="hover:text-ink">Contracts and source</Link>
          <a href="https://github.com/kenil1710/asvoted" className="hover:text-ink">GitHub</a>
        </p>
      </div>
    </footer>
  );
}
