import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Check, ChevronDown, Search } from "lucide-react";
import { useTranslation } from "react-i18next";

function normalizeText(value) {
  return String(value || "")
    .toLocaleLowerCase("uz")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[ʻ’`']/g, "")
    .replace(/[^a-z0-9а-яёқғҳў\s-]/gi, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function optionScore(option, rawQuery) {
  const query = normalizeText(rawQuery);
  if (!query) return 0;
  const label = normalizeText(option.label);
  const searchable = normalizeText([option.label, ...(option.searchTerms || [])].join(" "));
  if (label === query) return 1000;
  if (label.startsWith(query)) return 900 - label.length;
  if (label.split(" ").some((word) => word.startsWith(query))) return 800 - label.length;
  if (searchable.includes(query)) return 700 - searchable.indexOf(query);

  let searchIndex = 0;
  let distance = 0;
  for (const character of query) {
    const nextIndex = searchable.indexOf(character, searchIndex);
    if (nextIndex < 0) return -1;
    distance += nextIndex - searchIndex;
    searchIndex = nextIndex + 1;
  }
  return 400 - distance;
}

function normalizeOption(option) {
  if (typeof option === "string") return { value: option, label: option, searchTerms: [] };
  return {
    ...option,
    value: option.value ?? option.label ?? option.key,
    label: option.label ?? String(option.value ?? option.key ?? ""),
    searchTerms: option.searchTerms || option.aliases || [],
  };
}

export function SmartSelect({
  value,
  options = [],
  fallbackOptions = [],
  onChange,
  disabled = false,
  emptyLabel = "Tanlanmagan",
  fallbackLabel = "Butun katalogdan",
  ariaLabel,
}) {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage || i18n.language || "uz";
  const rootRef = useRef(null);
  const optionRefs = useRef([]);
  const listboxId = useId();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);

  const normalizedOptions = useMemo(() => options
    .map(normalizeOption)
    .map((option) => ({
      ...option,
      label: t(option.label, { defaultValue: option.label }),
      searchTerms: [option.label, option.value, option.key, ...(option.searchTerms || [])].filter(Boolean),
    }))
    .filter((option) => option.value !== undefined && option.value !== null && option.label)
    .map((option) => ({ ...option, recommended: true }))
    .sort((left, right) => left.label.localeCompare(right.label, language, { sensitivity: "base" })), [language, options, t]);

  const allOptions = useMemo(() => {
    const rows = new Map(normalizedOptions.map((option) => [String(option.value), option]));
    fallbackOptions
      .map(normalizeOption)
      .map((option) => ({
        ...option,
        label: t(option.label, { defaultValue: option.label }),
        searchTerms: [option.label, option.value, option.key, ...(option.searchTerms || [])].filter(Boolean),
      }))
      .filter((option) => option.value !== undefined && option.value !== null && option.label)
      .forEach((option) => {
        const key = String(option.value);
        if (!rows.has(key)) rows.set(key, { ...option, recommended: false });
      });
    return [...rows.values()].sort((left, right) => left.label.localeCompare(right.label, language, { sensitivity: "base" }));
  }, [fallbackOptions, language, normalizedOptions, t]);

  const selected = allOptions.find((option) => String(option.value) === String(value));
  const filteredOptions = useMemo(() => {
    if (!query.trim()) return normalizedOptions;
    return allOptions
      .map((option) => ({ option, score: optionScore(option, query) }))
      .filter((row) => row.score >= 0)
      .sort((left, right) => right.score - left.score || left.option.label.localeCompare(right.option.label, language))
      .map((row) => row.option);
  }, [allOptions, language, normalizedOptions, query]);

  useEffect(() => {
    function closeOnOutsidePointer(event) {
      if (!rootRef.current?.contains(event.target)) {
        setOpen(false);
        setQuery("");
      }
    }
    document.addEventListener("pointerdown", closeOnOutsidePointer);
    return () => document.removeEventListener("pointerdown", closeOnOutsidePointer);
  }, []);

  useEffect(() => {
    if (!open) return;
    setActiveIndex((current) => Math.min(current, Math.max(filteredOptions.length - 1, 0)));
  }, [filteredOptions.length, open]);

  useEffect(() => {
    if (!open) return;
    optionRefs.current[activeIndex]?.scrollIntoView({ block: "nearest" });
  }, [activeIndex, open]);

  function openMenu() {
    if (disabled) return;
    setOpen(true);
    setQuery("");
    const selectedIndex = normalizedOptions.findIndex((option) => String(option.value) === String(value));
    setActiveIndex(Math.max(selectedIndex, 0));
  }

  function selectOption(option) {
    onChange?.(option.value, option);
    setOpen(false);
    setQuery("");
  }

  function handleKeyDown(event) {
    if (disabled) return;
    if (!open && ["ArrowDown", "ArrowUp", "Enter", " "].includes(event.key)) {
      event.preventDefault();
      openMenu();
      return;
    }
    if (!open) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((current) => Math.min(current + 1, filteredOptions.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((current) => Math.max(current - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (filteredOptions[activeIndex]) selectOption(filteredOptions[activeIndex]);
    } else if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
      setQuery("");
    } else if (event.key === "Tab") {
      setOpen(false);
      setQuery("");
    }
  }

  return (
    <div className={open ? "smartSelect isOpen" : "smartSelect"} ref={rootRef}>
      <div className={disabled ? "smartSelectControl isDisabled" : "smartSelectControl"}>
        {open && <Search className="smartSelectSearchIcon" size={16} aria-hidden="true" />}
        <input
          className="smartSelectInput"
          role="combobox"
          aria-label={ariaLabel}
          aria-expanded={open}
          aria-controls={open ? listboxId : undefined}
          aria-activedescendant={open && filteredOptions[activeIndex] ? `${listboxId}-option-${activeIndex}` : undefined}
          aria-autocomplete="list"
          disabled={disabled}
          readOnly={!open}
          value={open ? query : selected?.label || ""}
          onFocus={openMenu}
          onClick={openMenu}
          onChange={(event) => {
            setQuery(event.target.value);
            setActiveIndex(0);
          }}
          onKeyDown={handleKeyDown}
        />
        {!open && !selected && <span className="smartSelectEmpty">{t(emptyLabel, { defaultValue: emptyLabel })}</span>}
        <ChevronDown className="smartSelectChevron" size={17} aria-hidden="true" />
      </div>

      {open && (
        <div className="smartSelectMenu" id={listboxId} role="listbox">
          <div className="smartSelectMeta">
            <span>{query ? `${t("Mos natijalar")}: ${filteredOptions.length}` : `${t("Barcha variantlar")}: ${filteredOptions.length}`}</span>
            <kbd>↑↓ Enter</kbd>
          </div>
          <div className="smartSelectOptions">
            {filteredOptions.map((option, index) => (
              <button
                className={index === activeIndex ? "smartSelectOption isActive" : "smartSelectOption"}
                type="button"
                role="option"
                id={`${listboxId}-option-${index}`}
                aria-selected={String(option.value) === String(value)}
                ref={(node) => { optionRefs.current[index] = node; }}
                key={String(option.value)}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => selectOption(option)}
              >
                <span className="smartSelectOptionText">
                  <strong>{option.label}</strong>
                  {query && !option.recommended && <small>{t(fallbackLabel, { defaultValue: fallbackLabel })}</small>}
                </span>
                {String(option.value) === String(value) && <Check size={16} />}
              </button>
            ))}
            {!filteredOptions.length && (
              <div className="smartSelectNoResults">{t("Yozilgan so‘zga mos variant topilmadi.")}</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
