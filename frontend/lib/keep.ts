"use client";

import { useCallback, useRef, useSyncExternalStore } from "react";


const values = new Map<string, unknown>();
const listeners = new Map<string, Set<() => void>>();
const stamps = new Map<string, number>();

function emit(key: string) {
    listeners.get(key)?.forEach((fn) => fn());
}

function subscribe(key: string, fn: () => void) {
    let set = listeners.get(key);
    if (!set) listeners.set(key, (set = new Set()));
    set.add(fn);
    return () => {
        set!.delete(fn);
    };
}

export function keptGet<T>(key: string): T | undefined {
    return values.get(key) as T | undefined;
}

export function keptSet<T>(key: string, value: T) {
    values.set(key, value);
    stamps.set(key, Date.now());
    emit(key);
}

export function keptAge(key: string): number {
    const t = stamps.get(key);
    return t === undefined ? Infinity : Date.now() - t;
}

export function keptReset() {
    const keys = Array.from(values.keys());
    values.clear();
    stamps.clear();
    keys.forEach(emit);
}

export function keptClear(prefix: string) {
    for (const k of Array.from(values.keys())) {
        if (k.startsWith(prefix)) {
            values.delete(k);
            stamps.delete(k);
            emit(k);
        }
    }
}

export function keptTrim(prefix: string, max: number) {
    const keys = Array.from(values.keys())
        .filter((k) => k.startsWith(prefix))
        .sort((a, b) => (stamps.get(b) ?? 0) - (stamps.get(a) ?? 0));
    for (const k of keys.slice(max)) {
        values.delete(k);
        stamps.delete(k);
    }
}

export function useKept<T>(key: string, initial: T | (() => T)): [T, (next: T | ((prev: T) => T)) => void] {
    const init = useRef<{ v: T } | null>(null);
    const initialValue = (): T => {
        if (init.current === null) init.current = { v: typeof initial === "function" ? (initial as () => T)() : initial };
        return init.current.v;
    };

    const sub = useCallback((fn: () => void) => subscribe(key, fn), [key])
    const getSnapshot = () => (values.has(key) ? (values.get(key) as T) : initialValue());
    const value = useSyncExternalStore(sub, getSnapshot, initialValue);

    const set = useCallback(
        (next: T | ((prev: T) => T)) => {
            const prev = values.has(key) ? (values.get(key) as T) : initialValue();
            const resolved = typeof next === "function" ? (next as (p: T) => T)(prev) : next;
            if (Object.is(resolved, prev) && values.has(key)) return;
            keptSet(key, resolved);
        },
        [key],
    );

    return[value, set];
}


