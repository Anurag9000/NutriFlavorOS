import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import AppLayout from "@/components/AppLayout";
import {
  PREPARATION_OPERATIONS_HANDOFF_KEY,
  type PreparationOperationsHandoff,
} from "@/lib/preparationOperationsHandoff";
import { preparationOperationsApi } from "@/lib/preparationOperationsApi";
import PreparationOperationsV2 from "@/pages/PreparationOperationsV2";

function pendingHandoff(): PreparationOperationsHandoff | null {
  const raw = sessionStorage.getItem(PREPARATION_OPERATIONS_HANDOFF_KEY);
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as PreparationOperationsHandoff;
    if (
      value.document_version !== "preparation-operations-handoff-v2"
      || !value.household_id
      || !value.bundle?.calendar_version_id
    ) {
      return null;
    }
    return value;
  } catch {
    return null;
  }
}

export default function PreparationOperationsPage() {
  const handoff = useMemo(pendingHandoff, []);
  const calendarQ = useQuery({
    queryKey: [
      "preparation-operations",
      handoff?.household_id,
      "calendar",
      handoff?.bundle.calendar_version_id,
    ],
    queryFn: () =>
      preparationOperationsApi.calendar(
        handoff!.household_id,
        handoff!.bundle.calendar_version_id,
      ),
    enabled: Boolean(handoff),
    retry: false,
  });

  if (handoff && calendarQ.isLoading) {
    return (
      <AppLayout>
        <main className="mx-auto grid min-h-[40vh] max-w-3xl place-items-center p-6">
          <p className="text-sm text-muted-foreground" aria-live="polite" aria-busy="true">
            Loading the exact reviewed calendar for structured operations review…
          </p>
        </main>
      </AppLayout>
    );
  }

  return <PreparationOperationsV2 />;
}
