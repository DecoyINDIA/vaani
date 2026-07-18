// Owner dashboard shell (ADR-07). Surfaces to build (TRD §5.2, Week 5 task 5.3):
// conversations + transcripts, bookings calendar, escalation inbox, settings
// (hours/services/fees/holidays), KB editor, daily counters.
export default function App() {
  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 p-8">
      <h1 className="text-2xl font-semibold">Vaani — Owner Dashboard</h1>
      <p className="mt-2 text-slate-600">
        Skeleton. Panels land in Week 5 (task 5.3): conversations, bookings,
        escalations, settings, KB editor, daily counters.
      </p>
    </main>
  );
}
