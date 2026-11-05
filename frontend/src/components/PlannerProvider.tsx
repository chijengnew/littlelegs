"use client";

import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { useTranslations } from "next-intl";
import { api, type Candidate, type CandidateResponse, type PlanResponse } from "@/lib/api/client";
import { toUiError, type UiError } from "@/lib/api/problem";
import { clearFlow, loadFlow, saveFlow } from "@/lib/flowStorage";
import { fieldFromLoc, initialForm, toConditions, validateForm, type FormErrors, type FormState } from "@/lib/form";
import { uuidv7 } from "@/lib/ids";
import { purgeOtherMembers } from "@/lib/packingStorage";
import { currentFirebaseUid } from "@/lib/firebaseClient";
import { useAuth } from "./AuthProvider";
import type { EditStop } from "./PlanView";

export type Step = "conditions" | "candidates" | "plan";

type PlannerValue = {
  step: Step;
  setStep: (s: Step) => void;
  form: FormState | null;
  setForm: (f: FormState) => void;
  errors: FormErrors;
  setErrors: (e: FormErrors) => void;
  apiError: UiError | null;
  busy: boolean;
  queryId: string | null;
  cands: CandidateResponse | null;
  selection: EditStop[];
  plan: PlanResponse | null;
  dirty: boolean;
  searched: boolean;
  importing: boolean;
  importError: UiError | null;
  clearImportError: () => void;
  resuming: boolean;
  loading: boolean;
  blocked: boolean;
  searchCandidates: (opts?: { resume?: boolean }) => Promise<boolean>;
  runPlan: (mode: "sort" | "check") => Promise<void>;
  toggle: (c: Candidate) => void;
  editStops: (next: EditStop[]) => void;
  editConditions: () => void;
  startFrom: (next: FormState) => void;
  resetAll: () => void;
};

const PlannerContext = createContext<PlannerValue | null>(null);

export function usePlanner(): PlannerValue {
  const value = useContext(PlannerContext);
  if (!value) throw new Error("PlannerProvider is required");
  return value;
}

type Resume = { target: "candidates" | "plan"; mode: "sort" | "check"; dirty: boolean };

export default function PlannerProvider({ children }: { children: ReactNode }) {
  const t = useTranslations();
  const auth = useAuth();
  const uid = auth.user?.uid ?? null;
  const [step, setStep] = useState<Step>("conditions");
  const [form, setForm] = useState<FormState | null>(null);
  const [errors, setErrors] = useState<FormErrors>({});
  const [apiError, setApiError] = useState<UiError | null>(null);
  const [busy, setBusy] = useState(false);
  const [queryId, setQueryId] = useState<string | null>(null);
  const [submittedKey, setSubmittedKey] = useState<string | null>(null);
  const [cands, setCands] = useState<CandidateResponse | null>(null);
  const [selection, setSelection] = useState<EditStop[]>([]);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [dirty, setDirty] = useState(false);
  const [searched, setSearched] = useState(false);
  const [ordered, setOrdered] = useState(false);
  const [revision, setRevision] = useState<number | null>(null);
  const [flowOwner, setFlowOwner] = useState<string | null>(uid);
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<UiError | null>(null);
  const [planMode, setPlanMode] = useState<"sort" | "check" | null>(null);
  const [resuming, setResuming] = useState(false);
  const resume = useRef<Resume | null>(null);
  const pendingPlan = useRef<Resume | null>(null);
  const previousUid = useRef(uid);
  const imports = useRef(new Map<string, ReturnType<typeof importGuestFlow>>());
  const restored = useRef(false);
  const inflight = useRef(0);
  const loading = !form || (flowOwner !== uid && flowOwner !== null);
  const blocked = busy || !auth.ready || importing || Boolean(auth.member && searched && revision === null);

  useEffect(() => {
    if (auth.booted) purgeOtherMembers(uid);
  }, [auth.booted, uid]);

  useEffect(() => {
    if (!auth.booted || restored.current) return;
    const v = loadFlow();
    previousUid.current = uid;
    /* eslint-disable react-hooks/set-state-in-effect */
    setFlowOwner(uid);
    if (v && (!v.ownerUid || v.ownerUid === uid)) {
      setForm({ ...initialForm(), ...v.form });
      setQueryId(v.queryId);
      setSubmittedKey(v.submittedKey);
      setSelection(v.selection);
      setSearched(v.searched ?? false);
      setOrdered(v.ordered ?? false);
      setPlanMode(v.planMode ?? null);
      if (v.searched && (v.step === "candidates" || v.step === "plan")) {
        resume.current = { target: v.step, mode: v.planMode ?? "sort", dirty: v.dirty ?? false };
        setStep(v.step);
        if (v.step === "plan" && v.dirty) setDirty(true);
        setResuming(true);
      }
    } else {
      clearFlow();
      setForm(initialForm());
    }
    /* eslint-enable react-hooks/set-state-in-effect */
    restored.current = true;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.booted]);

  useEffect(() => {
    if (!restored.current || previousUid.current === uid) return;
    const previous = previousUid.current;
    previousUid.current = uid;
    ++inflight.current;
    setBusy(false);
    setImporting(false);
    setImportError(null);
    setRevision(null);
    setFlowOwner(uid);
    resume.current = null;
    pendingPlan.current = null;
    setResuming(false);
    if (previous !== null) {
      clearFlow();
      setForm(initialForm());
      setQueryId(null);
      setSubmittedKey(null);
      setSelection([]);
      setCands(null);
      setPlan(null);
      setErrors({});
      setApiError(null);
      setSearched(false);
      setDirty(false);
      setOrdered(false);
      setPlanMode(null);
      setStep("conditions");
    }
  }, [uid]);

  useEffect(() => {
    if (!auth.member || !searched || !queryId || !submittedKey || revision !== null || importError || flowOwner !== uid || currentFirebaseUid() !== uid) return;
    let active = true;
    const key = `${uid}:${queryId}`;
    let work = imports.current.get(key);
    if (!work) {
      work = importGuestFlow(queryId, submittedKey, selection, ordered);
      imports.current.set(key, work);
      work.then(() => imports.current.delete(key), () => imports.current.delete(key));
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setImporting(true);
    work.then(({ data, error, response }) => {
      if (!active || currentFirebaseUid() !== uid) return;
      setImporting(false);
      if (data) setRevision(data.revision);
      else setImportError(toUiError(t, error, response.status));
    }).catch((error) => {
      if (active && currentFirebaseUid() === uid) {
        setImporting(false);
        setImportError(toUiError(t, error));
      }
    });
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.member?.id, searched, queryId, submittedKey, revision, importError, flowOwner, uid, t]);

  useEffect(() => {
    if (!restored.current || !form || flowOwner !== uid || !auth.ready) return;
    const r = resume.current ?? pendingPlan.current;
    saveFlow({
      form, queryId, submittedKey, selection, ownerUid: uid, searched, ordered,
      step: r?.target ?? step, planMode: r?.mode ?? planMode ?? undefined, dirty: r?.dirty ?? dirty,
    });
  }, [form, queryId, submittedKey, selection, flowOwner, uid, searched, ordered, auth.ready, step, planMode, dirty]);

  useEffect(() => {
    const r = resume.current;
    if (!r || !form || !auth.ready || blocked || flowOwner !== uid || currentFirebaseUid() !== uid) return;
    resume.current = null;
    if (r.target === "plan") pendingPlan.current = r;
    searchCandidates({ resume: true }).then((ok) => {
      if (!ok) {
        pendingPlan.current = null;
        setStep("conditions");
      }
      if (!ok || r.target === "candidates") setResuming(false);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form, auth.ready, blocked, flowOwner, uid]);

  useEffect(() => {
    const r = pendingPlan.current;
    if (!r || !cands || blocked) return;
    pendingPlan.current = null;
    /* eslint-disable react-hooks/set-state-in-effect */
    if (selection.length === 0) {
      setStep("candidates");
      setDirty(false);
      setResuming(false);
    } else if (r.dirty) setResuming(false);
    else runPlan(r.mode).finally(() => setResuming(false));
    /* eslint-enable react-hooks/set-state-in-effect */
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cands, blocked, selection.length]);

  function applyProblem(ue: UiError) {
    setApiError(ue);
    const fe: FormErrors = {};
    for (const e of ue.fieldErrors) {
      const k = fieldFromLoc(e.loc);
      if (k && !fe[k]) fe[k] = e.msg;
    }
    if (ue.code === "DEPARTURE_PASSED") fe.depart_time = "validation.departPast";
    if (Object.keys(fe).length) {
      setErrors(fe);
      setStep("conditions");
    }
  }

  async function searchCandidates({ resume = false }: { resume?: boolean } = {}): Promise<boolean> {
    if (!form || !auth.ready || busy || importing || currentFirebaseUid() !== uid) return false;
    const v = validateForm(form);
    setErrors(v);
    setApiError(null);
    if (Object.keys(v).length) {
      document.querySelector<HTMLElement>("[aria-invalid='true']")?.focus();
      return false;
    }
    const conditions = toConditions(form);
    const key = JSON.stringify(conditions);
    const qid = key === submittedKey && queryId ? queryId : uuidv7();
    if (qid !== queryId) { setSelection([]); setRevision(null); setSearched(false); setOrdered(false); }
    setImportError(null);
    setQueryId(qid);
    setSubmittedKey(key);
    setBusy(true);
    const my = ++inflight.current;
    try {
      const { data, error, response } = await api.POST("/v1/trips/candidates", {
        body: { query_id: qid, conditions },
      });
      if (my !== inflight.current || currentFirebaseUid() !== uid) return false;
      if (data) {
        setRevision(data.history?.revision ?? null);
        setSearched(true);
        setCands(data);
        setPlan(null);
        if (resume) {
          setSelection((sel) => sel.flatMap((x) => {
            const c = data.candidates.find((c) => c.place_id === x.place_id);
            return c ? [{ ...x, default_stay_minutes: c.default_stay.minutes }] : [];
          }));
        } else {
          setSelection([]);
          setOrdered(false);
          setDirty(false);
          setPlanMode(null);
          setStep("candidates");
        }
        return true;
      }
      applyProblem(toUiError(t, error, response.status));
    } catch (e) {
      if (my === inflight.current && currentFirebaseUid() === uid) applyProblem(toUiError(t, e));
    } finally {
      if (my === inflight.current) setBusy(false);
    }
    return false;
  }

  async function runPlan(mode: "sort" | "check") {
    if (!form || !queryId || selection.length === 0 || !auth.ready || busy || importing || currentFirebaseUid() !== uid || (auth.member && revision === null)) return;
    setApiError(null);
    setBusy(true);
    const my = ++inflight.current;
    const body = {
      query_id: queryId,
      conditions: toConditions(form),
      stops: selection.map((x) => ({ place_id: x.place_id, stay_minutes: x.stay_minutes })),
      ...(auth.member && revision !== null ? { expected_revision: revision } : {}),
    };
    try {
      const { data, error, response } =
        mode === "sort"
          ? await api.POST("/v1/trips/sort", { body })
          : await api.POST("/v1/trips/check", { body });
      if (my !== inflight.current || currentFirebaseUid() !== uid) return;
      if (data) {
        setRevision(data.history?.revision ?? null);
        setOrdered(true);
        setPlanMode(mode);
        setPlan(data);
        setDirty(false);
        const byId = new Map(selection.map((x) => [x.place_id, x]));
        setSelection(
          data.order
            .map((id) => byId.get(id))
            .filter((x): x is EditStop => Boolean(x)),
        );
        setStep("plan");
      } else applyProblem(toUiError(t, error, response.status));
    } catch (e) {
      if (my === inflight.current && currentFirebaseUid() === uid) applyProblem(toUiError(t, e));
    } finally {
      if (my === inflight.current) setBusy(false);
    }
  }

  function toggle(c: Candidate) {
    setSelection((sel) => {
      if (sel.some((x) => x.place_id === c.place_id)) return sel.filter((x) => x.place_id !== c.place_id);
      if (sel.length >= 5) return sel;
      return [...sel, { place_id: c.place_id, name: c.name, stay_minutes: null, default_stay_minutes: c.default_stay.minutes }];
    });
  }

  function editStops(next: EditStop[]) {
    setSelection(next);
    setDirty(true);
  }

  function editConditions() {
    setForm(initialForm());
    setErrors({});
    setApiError(null);
    setStep("conditions");
  }

  function startFrom(next: FormState) {
    resetAll();
    setForm(next);
  }

  function resetAll() {
    ++inflight.current;
    clearFlow();
    setForm(initialForm());
    setQueryId(null);
    setSubmittedKey(null);
    setSelection([]);
    setCands(null);
    setPlan(null);
    setErrors({});
    setApiError(null);
    setStep("conditions");
    setSearched(false);
    setRevision(null);
    setImportError(null);
    setImporting(false);
    setBusy(false);
    setOrdered(false);
    setPlanMode(null);
    resume.current = null;
    pendingPlan.current = null;
    setResuming(false);
  }

  const value: PlannerValue = {
    step, setStep, form, setForm, errors, setErrors, apiError, busy, queryId, cands, selection, plan, dirty, searched,
    importing, importError, clearImportError: () => setImportError(null), resuming, loading, blocked,
    searchCandidates, runPlan, toggle, editStops, editConditions, startFrom, resetAll,
  };
  return <PlannerContext.Provider value={value}>{children}</PlannerContext.Provider>;
}

async function importGuestFlow(queryId: string, key: string, selection: EditStop[], ordered: boolean) {
  return api.POST("/v1/histories/guest-import", { body: {
    query_id: queryId,
    conditions: JSON.parse(key),
    searched: true,
    ordered,
    stops: selection.map(({ place_id, stay_minutes }) => ({ place_id, stay_minutes })),
  } });
}
