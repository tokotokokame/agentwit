import { createContext, useContext } from 'react';
import { en } from './en';
import { ja } from './ja';
import type { Language } from '../types/mcp';

export type { Translations } from './en';

export const translations = { en, ja } as const;

export function getTranslations(language: Language) {
  return translations[language];
}

// i18n context
export const I18nContext = createContext<ReturnType<typeof getTranslations>>(en);

export function useI18n() {
  return useContext(I18nContext);
}

export { en, ja };
