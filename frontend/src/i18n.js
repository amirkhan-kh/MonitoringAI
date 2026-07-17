import { useEffect } from "react";
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { resources } from "./locales.js";

export const UI_LANGUAGE_KEY = "monitoring_ui_language";
export const SUPPORTED_LANGUAGES = ["uz", "ru", "en"];

function savedLanguage() {
  const value = window.localStorage.getItem(UI_LANGUAGE_KEY) || "uz";
  return SUPPORTED_LANGUAGES.includes(value) ? value : "uz";
}

i18n
  .use(initReactI18next)
  .init({
    resources,
    lng: savedLanguage(),
    fallbackLng: "uz",
    supportedLngs: SUPPORTED_LANGUAGES,
    keySeparator: false,
    nsSeparator: false,
    interpolation: { escapeValue: false },
    react: { useSuspense: false },
  });

const textState = new WeakMap();
const attributeState = new WeakMap();
const translatedAttributes = ["title", "aria-label"];

function dynamicTranslation(value, language) {
  const patterns = [
    [/^Mos natijalar: (\d+)$/, language === "ru" ? "Подходящие результаты: $1" : "Matching results: $1"],
    [/^Barcha variantlar: (\d+)$/, language === "ru" ? "Все варианты: $1" : "All options: $1"],
    [/^(\d+) source$/, language === "ru" ? "$1 источников" : "$1 sources"],
    [/^(\d+) hashtag$/, language === "ru" ? "$1 хэштегов" : "$1 hashtags"],
    [/^Yetishmaydi: (.+)$/, language === "ru" ? "Не заполнено: $1" : "Missing: $1"],
    [/^(“.+?”) source butunlay o'chirilsinmi\? Unga tegishli barcha post, comment, AI tahlil va alertlar ham o'chadi\. Bu amalni ortga qaytarib bo'lmaydi\.$/, language === "ru" ? "$1: полностью удалить источник? Все связанные публикации, комментарии, анализы ИИ и оповещения также будут удалены. Это действие нельзя отменить." : "$1: permanently delete this source? All related posts, comments, AI analyses, and alerts will also be deleted. This action cannot be undone."],
    [/^(“.+?”) source butunlay o'chirilsinmi\? Unga tegishli barcha video, comment va AI tahlillar ham o'chadi\. Bu amalni ortga qaytarib bo'lmaydi\.$/, language === "ru" ? "$1: полностью удалить источник? Все связанные видео, комментарии и анализы ИИ также будут удалены. Это действие нельзя отменить." : "$1: permanently delete this source? All related videos, comments, and AI analyses will also be deleted. This action cannot be undone."],
    [/^(“.+?”) source butunlay o'chirilsinmi\? Unga tegishli barcha post, comment va AI tahlillar ham o'chadi\. Bu amalni ortga qaytarib bo'lmaydi\.$/, language === "ru" ? "$1: полностью удалить источник? Все связанные публикации, комментарии и анализы ИИ также будут удалены. Это действие нельзя отменить." : "$1: permanently delete this source? All related posts, comments, and AI analyses will also be deleted. This action cannot be undone."],
    [/^(“.+?”) akkaunti butunlay o'chirilsinmi\? Unga tegishli barcha post, comment, @mention va AI tahlillar ham o'chadi\. Bu amalni ortga qaytarib bo'lmaydi\.$/, language === "ru" ? "$1: полностью удалить аккаунт? Все связанные публикации, комментарии, @mention и анализы ИИ также будут удалены. Это действие нельзя отменить." : "$1: permanently delete this account? All related posts, comments, @mentions, and AI analyses will also be deleted. This action cannot be undone."],
    [/^(“.+?”) sahifasi butunlay o'chirilsinmi\? Unga tegishli barcha post, comment, reply va AI tahlillar ham o'chadi\. Bu amalni ortga qaytarib bo'lmaydi\.$/, language === "ru" ? "$1: полностью удалить страницу? Все связанные публикации, комментарии, ответы и анализы ИИ также будут удалены. Это действие нельзя отменить." : "$1: permanently delete this page? All related posts, comments, replies, and AI analyses will also be deleted. This action cannot be undone."],
    [/^(\d+) ta source, (\d+) ta post\/comment va (\d+) ta AI tahlil(?: butunlay)? o'chirildi\.$/, language === "ru" ? "Удалено источников: $1, публикаций/комментариев: $2, анализов ИИ: $3." : "Deleted $1 sources, $2 posts/comments, and $3 AI analyses."],
    [/^(\d+) ta source, (\d+) ta video\/comment va (\d+) ta AI tahlil o'chirildi\.$/, language === "ru" ? "Удалено источников: $1, видео/комментариев: $2, анализов ИИ: $3." : "Deleted $1 sources, $2 videos/comments, and $3 AI analyses."],
    [/^(\d+) ta akkaunt, (\d+) ta post\/comment va (\d+) ta AI tahlil o'chirildi\.$/, language === "ru" ? "Удалено аккаунтов: $1, публикаций/комментариев: $2, анализов ИИ: $3." : "Deleted $1 accounts, $2 posts/comments, and $3 AI analyses."],
    [/^(\d+) ta sahifa, (\d+) ta post\/comment va (\d+) ta AI tahlil o'chirildi\.$/, language === "ru" ? "Удалено страниц: $1, публикаций/комментариев: $2, анализов ИИ: $3." : "Deleted $1 pages, $2 posts/comments, and $3 AI analyses."],
    [/^(\d+) ta komment AI tahlilga yuborildi\. Natijalar bir necha soniyada pastda ko'rinadi\.$/, language === "ru" ? "$1 комментариев отправлено на анализ ИИ. Результаты появятся ниже через несколько секунд." : "$1 comments were sent for AI analysis. Results will appear below in a few seconds."],
    [/^Serverga ulanib bo'lmadi \((.+)\)\. Backend ishga tushganini tekshiring\.$/, language === "ru" ? "Не удалось подключиться к серверу ($1). Проверьте, запущен ли backend." : "Could not connect to the server ($1). Check that the backend is running."],
  ];
  for (const [pattern, replacement] of patterns) {
    if (pattern.test(value)) return value.replace(pattern, replacement);
  }
  return value;
}

export function translateUiText(value, options = {}) {
  const source = String(value ?? "");
  const language = options.lng || i18n.resolvedLanguage || i18n.language || "uz";
  if (language === "uz" || !source.trim()) return source;
  if (i18n.exists(source, { lng: language })) {
    return i18n.t(source, { ...options, lng: language, defaultValue: source });
  }
  return dynamicTranslation(source, language);
}

function preserveWhitespace(source, translated) {
  const leading = source.match(/^\s*/)?.[0] || "";
  const trailing = source.match(/\s*$/)?.[0] || "";
  return `${leading}${translated}${trailing}`;
}

function localizeTextNode(node, language) {
  if (node.parentElement?.closest?.("[data-i18n-ignore='true']")) return;
  const current = node.nodeValue || "";
  let state = textState.get(node);
  if (!state || current !== state.rendered) state = { source: current, rendered: current };
  const trimmed = state.source.trim();
  const translated = trimmed ? preserveWhitespace(state.source, translateUiText(trimmed, { lng: language })) : state.source;
  state.rendered = translated;
  textState.set(node, state);
  if (current !== translated) node.nodeValue = translated;
}

function localizeAttributes(element, language) {
  const states = attributeState.get(element) || {};
  translatedAttributes.forEach((attribute) => {
    if (!element.hasAttribute(attribute)) return;
    const current = element.getAttribute(attribute) || "";
    const state = !states[attribute] || current !== states[attribute].rendered
      ? { source: current, rendered: current }
      : states[attribute];
    const translated = translateUiText(state.source, { lng: language });
    state.rendered = translated;
    states[attribute] = state;
    if (current !== translated) element.setAttribute(attribute, translated);
  });
  attributeState.set(element, states);
}

function localizeTree(root, language) {
  if (!root) return;
  if (root.nodeType === Node.TEXT_NODE) {
    localizeTextNode(root, language);
    return;
  }
  if (root.nodeType !== Node.ELEMENT_NODE) return;
  const element = root;
  if (element.closest?.("[data-i18n-ignore='true']")) return;
  localizeAttributes(element, language);
  const walker = document.createTreeWalker(element, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
  let node = walker.nextNode();
  while (node) {
    if (node.nodeType === Node.TEXT_NODE) localizeTextNode(node, language);
    else if (!node.closest?.("[data-i18n-ignore='true']")) localizeAttributes(node, language);
    node = walker.nextNode();
  }
}

export function useDomLocalization(language) {
  useEffect(() => {
    const root = document.getElementById("root");
    document.documentElement.lang = language;
    window.localStorage.setItem(UI_LANGUAGE_KEY, language);
    localizeTree(root, language);
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.type === "characterData") localizeTextNode(mutation.target, language);
        if (mutation.type === "attributes") localizeAttributes(mutation.target, language);
        mutation.addedNodes.forEach((node) => localizeTree(node, language));
      });
    });
    observer.observe(root, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeFilter: translatedAttributes,
    });
    return () => observer.disconnect();
  }, [language]);
}

export function formatUiDate(value, options = {}) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return value || "";
  const language = i18n.resolvedLanguage || i18n.language || "uz";
  const locale = { uz: "uz-UZ", ru: "ru-RU", en: "en-US" }[language] || "uz-UZ";
  return new Intl.DateTimeFormat(locale, options).format(date);
}

export default i18n;
