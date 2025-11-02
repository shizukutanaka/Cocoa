type Language = 'en' | 'ja' | 'ko' | 'zh' | 'es' | 'fr' | 'de' | 'hi' | 'id' | 'ar';

interface TranslationKeys {
  'common.save': string;
  'common.cancel': string;
  'common.loading': string;
  'common.error': string;
  'avatar.style': string;
  'avatar.complexity': string;
  'avatar.colors': string;
  'avatar.generate': string;
  'avatar.preview': string;
}

type Translations = Record<Language, TranslationKeys>;

const translations: Translations = {
  en: {
    'common.save': 'Save',
    'common.cancel': 'Cancel',
    'common.loading': 'Loading...',
    'common.error': 'Error',
    'avatar.style': 'Avatar Style',
    'avatar.complexity': 'Complexity Level',
    'avatar.colors': 'Colors',
    'avatar.generate': 'Generate Avatar',
    'avatar.preview': 'Preview',
  },
  ja: {
    'common.save': '保存',
    'common.cancel': 'キャンセル',
    'common.loading': '読み込み中...',
    'common.error': 'エラー',
    'avatar.style': 'アバタースタイル',
    'avatar.complexity': '複雑さレベル',
    'avatar.colors': '色',
    'avatar.generate': 'アバターを生成',
    'avatar.preview': 'プレビュー',
  },
  ko: {
    'common.save': '저장',
    'common.cancel': '취소',
    'common.loading': '로딩 중...',
    'common.error': '오류',
    'avatar.style': '아바타 스타일',
    'avatar.complexity': '복잡성 수준',
    'avatar.colors': '색상',
    'avatar.generate': '아바타 생성',
    'avatar.preview': '미리보기',
  },
  zh: {
    'common.save': '保存',
    'common.cancel': '取消',
    'common.loading': '加载中...',
    'common.error': '错误',
    'avatar.style': '头像风格',
    'avatar.complexity': '复杂度级别',
    'avatar.colors': '颜色',
    'avatar.generate': '生成头像',
    'avatar.preview': '预览',
  },
  es: {
    'common.save': 'Guardar',
    'common.cancel': 'Cancelar',
    'common.loading': 'Cargando...',
    'common.error': 'Error',
    'avatar.style': 'Estilo de Avatar',
    'avatar.complexity': 'Nivel de Complejidad',
    'avatar.colors': 'Colores',
    'avatar.generate': 'Generar Avatar',
    'avatar.preview': 'Vista Previa',
  },
  fr: {
    'common.save': 'Enregistrer',
    'common.cancel': 'Annuler',
    'common.loading': 'Chargement...',
    'common.error': 'Erreur',
    'avatar.style': 'Style d\'Avatar',
    'avatar.complexity': 'Niveau de Complexité',
    'avatar.colors': 'Couleurs',
    'avatar.generate': 'Générer l\'Avatar',
    'avatar.preview': 'Aperçu',
  },
  de: {
    'common.save': 'Speichern',
    'common.cancel': 'Abbrechen',
    'common.loading': 'Laden...',
    'common.error': 'Fehler',
    'avatar.style': 'Avatar-Stil',
    'avatar.complexity': 'Komplexitätsstufe',
    'avatar.colors': 'Farben',
    'avatar.generate': 'Avatar Generieren',
    'avatar.preview': 'Vorschau',
  },
  hi: {
    'common.save': 'सहेजें',
    'common.cancel': 'रद्द करें',
    'common.loading': 'लोड हो रहा है...',
    'common.error': 'त्रुटि',
    'avatar.style': 'अवतार शैली',
    'avatar.complexity': 'जटिलता स्तर',
    'avatar.colors': 'रंग',
    'avatar.generate': 'अवतार उत्पन्न करें',
    'avatar.preview': 'पूर्वावलोकन',
  },
  id: {
    'common.save': 'Simpan',
    'common.cancel': 'Batal',
    'common.loading': 'Memuat...',
    'common.error': 'Kesalahan',
    'avatar.style': 'Gaya Avatar',
    'avatar.complexity': 'Tingkat Kompleksitas',
    'avatar.colors': 'Warna',
    'avatar.generate': 'Buat Avatar',
    'avatar.preview': 'Pratinjau',
  },
  ar: {
    'common.save': 'حفظ',
    'common.cancel': 'إلغاء',
    'common.loading': 'جارٍ التحميل...',
    'common.error': 'خطأ',
    'avatar.style': 'نمط الأفاتار',
    'avatar.complexity': 'مستوى التعقيد',
    'avatar.colors': 'الألوان',
    'avatar.generate': 'إنشاء الأفاتار',
    'avatar.preview': 'معاينة',
  },
};

export const useTranslation = (language: Language) => {
  const t = (key: keyof TranslationKeys): string => {
    return translations[language]?.[key] || translations.en[key] || key;
  };

  return { t, language };
};

export type { Language, TranslationKeys };
export { translations };
