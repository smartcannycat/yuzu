import type {
  AnomalyAlert,
  BodyPanel,
  ChecklistItemStatus,
  CrossAuditReport,
  CustomsCalculation,
  DamagedPartItem,
  EconomicsDetail,
  FarpostRepairSummary,
  FuelType,
  LotDetailResponse,
  LotSummary,
  NormalizedDefect,
  NormalizedSheet,
  PastAuctionRecord,
  RecalculateRequest,
  RecalculateResponse,
  RiskFlags,
  SafetyCheckItem,
  SafetyChecklist,
  ServiceWorkItem,
  TrafficLightColor,
  TrafficLightVerdict,
  WiseCostStep,
} from '@/types/api'
import { formatRub } from '@/utils/formatters'

interface PresetDetailConfig {
  trim: string | null
  modelCode: string
  auctionBranch: string
  strictness: number
  powerHp: number
  fuelType: FuelType
  driveType: '2WD' | '4WD'
  transmission: string
  colorRu: string
  paintCode: string
  exteriorGrade: string
  interiorGrade: string
  shakenUntil: string | null
  recyclingYen: number
  equipment: string[]
  defects: NormalizedDefect[]
  parts: DamagedPartItem[]
  serviceWorks: ServiceWorkItem[]
  bodySummaryRu: string
  interiorSummaryRu: string
  reasoningBullets: string[]
  inspectorNotesRu: string[]
  inspectorNotesRaw: string[]
  sellerCommentsRu: string[]
  ocrWarnings: string[]
  analogsCount: number
  anomalies: AnomalyAlert[]
  history: PastAuctionRecord[]
  hasCriticalAnomaly: boolean
  isCommercialUtilDefault?: boolean
  riskFlagsOverride?: Partial<RiskFlags>
}

const DEFAULT_RISK_FLAGS: RiskFlags = {
  is_flooded: false,
  airbag_deployed: false,
  hail_damage: false,
  underbody_corrosion: false,
  pillar_or_frame_repair: false,
  underbody_rust: false,
  panel_needs_replacement_x: false,
  panel_replaced_xx: false,
  odometer_issue: false,
  color_changed: false,
  windshield_damage: false,
  repaired_grade_r_ra: false,
}

const JPY_RUB_RATE = 0.642
const EUR_RUB_RATE = 95.0
const USD_RUB_RATE = 88.5
const COMMERCIAL_UTIL_FEE_RUB = 528_000
const PERSONAL_UTIL_FEE_RUB = 5_200

const PANEL_LABELS_RU: Record<BodyPanel, string> = {
  front_bumper: 'Передний бампер',
  rear_bumper: 'Задний бампер',
  hood: 'Капот',
  roof: 'Крыша',
  tailgate: 'Пятая дверь / крышка багажника',
  front_left_fender: 'Переднее левое крыло',
  front_right_fender: 'Переднее правое крыло',
  front_left_door: 'Передняя левая дверь',
  front_right_door: 'Передняя правая дверь',
  rear_left_door: 'Задняя левая дверь',
  rear_right_door: 'Задняя правая дверь',
  rear_left_quarter: 'Заднее левое крыло',
  rear_right_quarter: 'Заднее правое крыло',
  left_sill: 'Левый порог',
  right_sill: 'Правый порог',
  windshield: 'Лобовое стекло',
}

const PRESET_CONFIGS: Record<string, PresetDetailConfig> = {
  '892b4e10-3a2c-411f-a801-019283746501': {
    trim: 'W×B Hybrid',
    modelCode: '6AA-ZWE211W',
    auctionBranch: 'TAA Chubu',
    strictness: 1.0,
    powerHp: 122,
    fuelType: 'hybrid',
    driveType: '2WD',
    transmission: 'Вариатор (e-CVT)',
    colorRu: 'Белый перламутр',
    paintCode: '070',
    exteriorGrade: 'B',
    interiorGrade: 'B',
    shakenUntil: '10.2027',
    recyclingYen: 10940,
    equipment: [
      'Toyota Safety Sense',
      'LED-оптика',
      'Двухзонный климат-контроль',
      'Камера заднего вида',
      'Подогрев сидений',
      'Литые диски R17',
    ],
    defects: [
      {
        panel_id: 'front_left_door',
        panel_ru: PANEL_LABELS_RU.front_left_door,
        defect_types: ['XX'],
        severity: null,
        raw_code: 'XX',
        description_ru: 'Передняя левая дверь — менялась в Японии (болтовая навесная деталь)',
      },
      {
        panel_id: 'front_bumper',
        panel_ru: PANEL_LABELS_RU.front_bumper,
        defect_types: ['A'],
        severity: 2,
        raw_code: 'A2',
        description_ru: 'Передний бампер — потёртость нижней губы слева (~15 см)',
      },
      {
        panel_id: 'rear_right_quarter',
        panel_ru: PANEL_LABELS_RU.rear_right_quarter,
        defect_types: ['U'],
        severity: 1,
        raw_code: 'U1',
        description_ru: 'Заднее правое крыло — мелкая вмятина без повреждения ЛКП (PDR)',
      },
    ],
    parts: [
      {
        panel_id: 'front_left_door',
        defect_code: 'XX',
        part_name_ru: 'Передняя левая дверь (контрактная, код краски 070)',
        subtitle_ru: 'В наличии во Владивостоке · в заводской цвет без перекраса',
        price_from_rub: 18000,
        in_stock_vladivostok: true,
        is_statistical_fallback: false,
      },
    ],
    serviceWorks: [
      {
        work_type: 'mount_dismount',
        label_ru: 'Регулировка зазоров и проверка навески двери',
        amount_rub: 4000,
        zero_cost_reason_ru: null,
      },
      {
        work_type: 'paint',
        label_ru: 'Окрас детали',
        amount_rub: 0,
        zero_cost_reason_ru: 'не требуется (деталь найдена в цвет 070)',
      },
      {
        work_type: 'pdr_and_polish',
        label_ru: 'Локальная полировка бампера и PDR заднего крыла',
        amount_rub: 9000,
        zero_cost_reason_ru: null,
      },
    ],
    bodySummaryRu: 'Замена передней левой двери без захода на стойки, косметика A2/U1',
    interiorSummaryRu: 'Салон B — чистый, без посторонних запахов, лёгкий износ руля',
    reasoningBullets: [
      'Аукционный дом высшей строгости TAA Chubu (индекс строгости 1.00)',
      'Пробег 62 000 км подтверждён первичной регистрацией и сервисной историей',
      'Дверь подобрана в заводской цвет 070 во Владивостоке без дорогостоящей покраски',
      'Мощность 122 л.с. укладывается в порог 160 л.с. (льготный утильсбор 5 200 ₽)',
    ],
    inspectorNotesRu: [
      'Передняя левая дверь заменена в Японии (навесная деталь, петли и стойка без ремонта)',
      'Мелкие царапины по нижней кромке переднего бампера',
      'Салон чистый, потолок и обшивка дверей без прожогов',
      'Сервисная книжка и два смарт-ключа в комплекте',
    ],
    inspectorNotesRaw: [
      '左Fドア交換跡あり（ピラー異常なし）',
      'Fバンパー下部スリキズ',
      '室内キレイ・スマートキー2本',
    ],
    sellerCommentsRu: ['Один владелец в Японии', 'Обслуживание у дилера Toyota'],
    ocrWarnings: [],
    analogsCount: 14,
    anomalies: [],
    history: [
      {
        auction_date: '24.05.2026',
        auction_house: 'TAA Chubu',
        auction_strictness: 1.0,
        lot_number: '3142',
        overall_grade: '4',
        mileage_km: 62000,
        defects_summary: 'XX лев. передн. дверь, A2 передн. бампер',
        closing_price_jpy: 1240000,
        sheet_archive_url: null,
      },
    ],
    hasCriticalAnomaly: false,
    riskFlagsOverride: { panel_replaced_xx: true },
  },
  '892b4e10-3a2c-411f-a801-019283746502': {
    trim: 'e:HEV Z',
    modelCode: '6AA-RV5',
    auctionBranch: 'USS Tokyo',
    strictness: 0.78,
    powerHp: 131,
    fuelType: 'hybrid',
    driveType: '2WD',
    transmission: 'Редуктор e:HEV',
    colorRu: 'Серый металлик',
    paintCode: 'NH883P',
    exteriorGrade: 'A',
    interiorGrade: 'A',
    shakenUntil: '08.2027',
    recyclingYen: 11400,
    equipment: [
      'Honda Sensing',
      'Адаптивный круиз-контроль',
      'Электропривод багажника',
      'Беспроводная зарядка',
      'Подогрев руля и сидений',
    ],
    defects: [
      {
        panel_id: 'rear_bumper',
        panel_ru: PANEL_LABELS_RU.rear_bumper,
        defect_types: ['A'],
        severity: 1,
        raw_code: 'A1',
        description_ru: 'Задний бампер — незаметная микроцарапина у порога погрузки',
      },
    ],
    parts: [],
    serviceWorks: [
      {
        work_type: 'pdr_and_polish',
        label_ru: 'Лёгкая предпродажная полировка заднего бампера',
        amount_rub: 4500,
        zero_cost_reason_ru: null,
      },
    ],
    bodySummaryRu: 'Практически идеальный кузов оценки A — только мелкий скол A1 на бампере',
    interiorSummaryRu: 'Салон A — без потёртостей, состояние близкое к новому авто',
    reasoningBullets: [
      'Высокий общий балл 4.5 и оценки кузова/салона A/A',
      'Проходной возраст 3–5 лет с минимальной пошлиной по объёму 1 496 см³',
      'Мощность 131 л.с. сохраняет льготный утильсбор 5 200 ₽',
    ],
    inspectorNotesRu: [
      'На кузове только незначительные следы эксплуатации (A1)',
      'Электроника и гибридная батарея без ошибок по диагностике',
    ],
    inspectorNotesRaw: ['外装極上 A1のみ', 'HVシステム正常'],
    sellerCommentsRu: ['Гаражное хранение', 'Зимняя резина в багажнике не прилагается'],
    ocrWarnings: [],
    analogsCount: 19,
    anomalies: [],
    history: [
      {
        auction_date: '18.05.2026',
        auction_house: 'USS Tokyo',
        auction_strictness: 0.78,
        lot_number: '8412',
        overall_grade: '4.5',
        mileage_km: 38000,
        defects_summary: 'A1 задний бампер',
        closing_price_jpy: 1640000,
        sheet_archive_url: null,
      },
    ],
    hasCriticalAnomaly: false,
  },
  '892b4e10-3a2c-411f-a801-019283746503': {
    trim: 'X e-Power',
    modelCode: '6AA-E13',
    auctionBranch: 'CAA Chubu',
    strictness: 0.85,
    powerHp: 116,
    fuelType: 'hybrid',
    driveType: '2WD',
    transmission: 'Редуктор e-Power',
    colorRu: 'Чёрный металлик',
    paintCode: 'KH3',
    exteriorGrade: 'C',
    interiorGrade: 'B',
    shakenUntil: '03.2027',
    recyclingYen: 9850,
    equipment: [
      'ProPILOT',
      'Камеры кругового обзора 360°',
      'Климат-контроль',
      'Бесключевой доступ',
    ],
    defects: [
      {
        panel_id: 'tailgate',
        panel_ru: PANEL_LABELS_RU.tailgate,
        defect_types: ['W'],
        severity: 2,
        raw_code: 'W2',
        description_ru: 'Пятая дверь — вторичный окрас с заметным переходом лака (W2)',
      },
      {
        panel_id: 'rear_bumper',
        panel_ru: PANEL_LABELS_RU.rear_bumper,
        defect_types: ['XX'],
        severity: null,
        raw_code: 'XX',
        description_ru: 'Задний бампер — заменялся ранее (незначительный люфт крепления справа)',
      },
      {
        panel_id: 'front_right_door',
        panel_ru: PANEL_LABELS_RU.front_right_door,
        defect_types: ['U'],
        severity: 2,
        raw_code: 'U2',
        description_ru: 'Передняя правая дверь — вмятина размером ~6 см по ребру жёсткости',
      },
    ],
    parts: [
      {
        panel_id: 'rear_bumper',
        defect_code: 'XX',
        part_name_ru: 'Кронштейн и ревизия заднего бампера (KH3)',
        subtitle_ru: 'Контрактный узел в цвет во Владивостоке',
        price_from_rub: 12000,
        in_stock_vladivostok: true,
        is_statistical_fallback: false,
      },
    ],
    serviceWorks: [
      {
        work_type: 'paint',
        label_ru: 'Локальная полировка и перепыл пятой двери W2',
        amount_rub: 14000,
        zero_cost_reason_ru: null,
      },
      {
        work_type: 'bodywork',
        label_ru: 'Вытяжка вмятины на правой двери + регулировка бампера',
        amount_rub: 11000,
        zero_cost_reason_ru: null,
      },
    ],
    bodySummaryRu: 'Вторичный окрас пятой двери W2 и замена заднего бампера, силовая цела',
    interiorSummaryRu: 'Салон B — аккуратный, незначительные следы на пластике багажника',
    reasoningBullets: [
      'Требуется проверка зазоров крышки багажника и качества окраса W2',
      'Чистая экономическая выгода невысока (+75 000 ₽) — критично не переплачивать на ставке',
    ],
    inspectorNotesRu: [
      'Пятая дверь имеет следы вторичного окраса (W2)',
      'Задний бампер заменён, панель пола багажника без деформаций',
      'Мелкая вмятина U2 на передней правой двери',
    ],
    inspectorNotesRaw: ['バックドア塗装跡 W2', 'Rバンパー交換', '右Fドア U2'],
    sellerCommentsRu: ['Недавно пройдено ТО в Японии'],
    ocrWarnings: [],
    analogsCount: 11,
    anomalies: [
      {
        type: 'unreported_defects',
        severity: 'warning',
        title_ru: 'Следы косметического ремонта сзади (W2 / XX)',
        message_ru:
          'На предыдущих торгах в 2025 г. задний бампер имел притёртость A3; перед перевыставлением бампер заменили и подкрасили пятую дверь.',
        diff_details: {
          archived_val: 'Бампер A3, дверь целая',
          current_val: 'Бампер XX, дверь W2',
        },
      },
    ],
    history: [
      {
        auction_date: '09.11.2025',
        auction_house: 'USS Nagoya',
        auction_strictness: 0.78,
        lot_number: '1408',
        overall_grade: '3.5',
        mileage_km: 79200,
        defects_summary: 'A3 задний бампер, U2 правая дверь',
        closing_price_jpy: 860000,
        sheet_archive_url: null,
      },
    ],
    hasCriticalAnomaly: false,
    riskFlagsOverride: { panel_replaced_xx: true },
  },
  '892b4e10-3a2c-411f-a801-019283746504': {
    trim: 'Hybrid Z Leather',
    modelCode: '6AA-AXUH80',
    auctionBranch: 'JU Aichi',
    strictness: 0.6,
    powerHp: 178,
    fuelType: 'hybrid',
    driveType: '2WD',
    transmission: 'Вариатор (e-CVT)',
    colorRu: 'Чёрный',
    paintCode: '202',
    exteriorGrade: 'D',
    interiorGrade: 'C',
    shakenUntil: null,
    recyclingYen: 13200,
    equipment: [
      'Кожаный салон',
      'Акустика JBL',
      'Память водительского сиденья',
      'Вентиляция передних кресел',
    ],
    defects: [
      {
        panel_id: 'rear_left_quarter',
        panel_ru: PANEL_LABELS_RU.rear_left_quarter,
        defect_types: ['XX'],
        severity: null,
        raw_code: 'XX',
        description_ru:
          'Заднее левое крыло — вырезка и вварка четверти, швы в нише багажника (оценка R)',
      },
      {
        panel_id: 'left_sill',
        panel_ru: PANEL_LABELS_RU.left_sill,
        defect_types: ['W', 'U'],
        severity: 3,
        raw_code: 'W3/U3',
        description_ru: 'Левый порог — тяжёлая рихтовка и толстый слой шпатлёвки',
      },
      {
        panel_id: 'windshield',
        panel_ru: PANEL_LABELS_RU.windshield,
        defect_types: ['A'],
        severity: 2,
        raw_code: 'G',
        description_ru: 'Лобовое стекло — скол/трещина со стороны пассажира (риск для СБКТС)',
      },
    ],
    parts: [
      {
        panel_id: 'windshield',
        defect_code: 'G',
        part_name_ru: 'Лобовое стекло с обогревом зоны щёток',
        subtitle_ru: 'Необходимо для прохождения лаборатории СБКТС',
        price_from_rub: 29000,
        in_stock_vladivostok: true,
        is_statistical_fallback: false,
      },
      {
        panel_id: 'rear_left_quarter',
        defect_code: 'XX',
        part_name_ru: 'Герметизация и антикор швов задней арки/багажника',
        subtitle_ru: 'Статистическая оценка кузовного участка',
        price_from_rub: 19000,
        in_stock_vladivostok: false,
        is_statistical_fallback: true,
      },
    ],
    serviceWorks: [
      {
        work_type: 'bodywork',
        label_ru: 'Стапельная проверка геометрии и обработка левого порога',
        amount_rub: 38000,
        zero_cost_reason_ru: null,
      },
      {
        work_type: 'paint',
        label_ru: 'Перекрас левого порога и заднего крыла',
        amount_rub: 24000,
        zero_cost_reason_ru: null,
      },
    ],
    bodySummaryRu: 'Критично: оценка R, вварка заднего левого крыла и следы сварки в багажнике',
    interiorSummaryRu: 'Салон C — потёртость боковины водительского сиденья, царапины пластика',
    reasoningBullets: [
      'Безусловный стоп-фактор: восстановление силовой структуры (задняя стойка / ниша багажника)',
      'Аукционный кросс-аудит выявил расхождение пробега относительно архивных торгов',
      'Объём 2 487 см³ и мощность 178 л.с. — риск санкций METI и повышенный утильсбор',
      'Отрицательная экономика (-110 000 ₽) даже до учёта скрытых кузовных рисков',
    ],
    inspectorNotesRu: [
      'Следы ремонта и сварки в левой задней стойке и нише запасного колеса (оценка R)',
      'Коррозийный налёт на элементах задней подвески',
      'Треснувшее лобовое стекло (требуется замена перед СБКТС)',
    ],
    inspectorNotesRaw: ['左Rピラー修理跡・トランクフロア歪み', 'Fガラスヒビ', '下廻りサビ'],
    sellerCommentsRu: ['Продаётся как есть (現状販売)'],
    ocrWarnings: ['На листе JU применена сокращённая запись номера кузова'],
    analogsCount: 9,
    anomalies: [
      {
        type: 'odometer_rollback',
        severity: 'critical',
        title_ru: 'Подозрение на скрученный пробег (-34 000 км)',
        message_ru:
          'На архивных торгах TAA Kinki 12.01.2026 зафиксирован пробег 132 000 км. На текущем аукционе JU заявлено 98 000 км.',
        diff_details: {
          archived_val: '132 000 км',
          current_val: '98 000 км',
          delta_km: -34000,
        },
      },
      {
        type: 'concealed_salvage_r',
        severity: 'critical',
        title_ru: 'Сложный силовой ремонт в прошлом',
        message_ru:
          'На строгой площадке TAA зафиксированы деформация задней стойки и складка пола багажника. При переносе на JU часть комментариев сокращена.',
        diff_details: {
          archived_grade: 'R (TAA Kinki)',
          current_grade: 'R (JU Aichi)',
        },
      },
    ],
    history: [
      {
        auction_date: '12.01.2026',
        auction_house: 'TAA Kinki',
        auction_strictness: 1.0,
        lot_number: '9102',
        overall_grade: 'R',
        mileage_km: 132000,
        defects_summary: 'XX задн. лев. крыло, деформация стойки и пола багажника',
        closing_price_jpy: 1920000,
        sheet_archive_url: null,
      },
      {
        auction_date: '04.04.2026',
        auction_house: 'JU Aichi',
        auction_strictness: 0.6,
        lot_number: '5519',
        overall_grade: 'R',
        mileage_km: 98000,
        defects_summary: 'Следы ремонта сзади слева, скол G лобового',
        closing_price_jpy: null,
        sheet_archive_url: null,
      },
    ],
    hasCriticalAnomaly: true,
    isCommercialUtilDefault: false,
    riskFlagsOverride: {
      pillar_or_frame_repair: true,
      repaired_grade_r_ra: true,
      odometer_issue: true,
      windshield_damage: true,
      underbody_rust: true,
      panel_replaced_xx: true,
    },
  },
  '892b4e10-3a2c-411f-a801-019283746505': {
    trim: 'GT-H EX',
    modelCode: '4BA-VN5',
    auctionBranch: 'USS Sapporo',
    strictness: 0.78,
    powerHp: 177,
    fuelType: 'gasoline',
    driveType: '4WD',
    transmission: 'Lineartronic CVT',
    colorRu: 'Синий металлик',
    paintCode: 'K7X',
    exteriorGrade: 'B',
    interiorGrade: 'B',
    shakenUntil: '11.2026',
    recyclingYen: 12100,
    equipment: [
      'EyeSight X',
      'Постоянный полный привод',
      'Цифровая приборная панель 12.3"',
      'Светодиодные фары',
    ],
    defects: [
      {
        panel_id: 'hood',
        panel_ru: PANEL_LABELS_RU.hood,
        defect_types: ['A'],
        severity: 1,
        raw_code: 'A1',
        description_ru: 'Капот — несколько мелких сколов от гравия',
      },
      {
        panel_id: 'right_sill',
        panel_ru: PANEL_LABELS_RU.right_sill,
        defect_types: ['S'],
        severity: 1,
        raw_code: 'S1',
        description_ru: 'Правый порог — лёгкий поверхностный налёт ржавчины снизу (S1)',
      },
    ],
    parts: [],
    serviceWorks: [
      {
        work_type: 'bodywork',
        label_ru: 'Антикоррозийная обработка днища и порогов во Владивостоке',
        amount_rub: 15000,
        zero_cost_reason_ru: null,
      },
    ],
    bodySummaryRu: 'Ровный кузов 4 балла, отмечен только лёгкий налёт S1 по днищу (Хоккайдо)',
    interiorSummaryRu: 'Салон B — аккуратный, без посторонних запахов',
    reasoningBullets: [
      'Мощность 177 л.с. (> 160 л.с.) — требуется закладывать повышенный утильсбор',
      'Маржа к рынку РФ (+90 000 ₽) небольшая — покупка оправдана только при снижении ставки',
    ],
    inspectorNotesRu: [
      'Лёгкая поверхностная ржавчина по днищу и правому порогу (S1)',
      'Система EyeSight и полный привод работают исправно',
    ],
    inspectorNotesRaw: ['下廻り軽度サビ S1', 'アイサイト正常'],
    sellerCommentsRu: ['Один владелец', 'Электронная сервисная книга'],
    ocrWarnings: [],
    analogsCount: 7,
    anomalies: [],
    history: [
      {
        auction_date: '29.05.2026',
        auction_house: 'USS Sapporo',
        auction_strictness: 0.78,
        lot_number: '1045',
        overall_grade: '4',
        mileage_km: 51000,
        defects_summary: 'S1 днище/порог, A1 капот',
        closing_price_jpy: 1710000,
        sheet_archive_url: null,
      },
    ],
    hasCriticalAnomaly: false,
    riskFlagsOverride: { underbody_rust: true },
  },
  '892b4e10-3a2c-411f-a801-019283746506': {
    trim: 'XD L Package',
    modelCode: '3DA-KF2P',
    auctionBranch: 'ARAI Bayside',
    strictness: 0.88,
    powerHp: 190,
    fuelType: 'diesel',
    driveType: '4WD',
    transmission: '6-ступ. АКПП',
    colorRu: 'Красный Soul Red',
    paintCode: '46V',
    exteriorGrade: 'A',
    interiorGrade: 'B',
    shakenUntil: '07.2027',
    recyclingYen: 13650,
    equipment: [
      'i-Activsense',
      'Проекционный дисплей HUD',
      'Акустика Bose',
      'Кожа Nappa',
      'Круговой обзор 360°',
    ],
    defects: [
      {
        panel_id: 'front_right_fender',
        panel_ru: PANEL_LABELS_RU.front_right_fender,
        defect_types: ['A'],
        severity: 1,
        raw_code: 'A1',
        description_ru: 'Переднее правое крыло — едва заметная поверхностная риска',
      },
    ],
    parts: [],
    serviceWorks: [
      {
        work_type: 'pdr_and_polish',
        label_ru: 'Детейлинг-полировка кузова',
        amount_rub: 8000,
        zero_cost_reason_ru: null,
      },
    ],
    bodySummaryRu: 'Отличное состояние 4.5 балла, кузов без окрасов и замен (A/B)',
    interiorSummaryRu: 'Салон B — чистая кожа Nappa, ухоженная передняя панель',
    reasoningBullets: [
      'Двигатель 2 188 см³ попадает под экспортные ограничения METI — нужен транзитный маршрут через третьи страны',
      'Выгода +250 000 ₽ к рынку РФ сохраняется даже с учётом логистики',
    ],
    inspectorNotesRu: [
      'Кузов в заводском окрасе, отмечена одна микроцарапина A1',
      'Требуется согласование транзитной логистики из-за объёма 2.2 л (METI)',
    ],
    inspectorNotesRaw: ['外装良好 A1のみ', '機関良好'],
    sellerCommentsRu: ['Полный комплект ключей', 'Не курили в салоне'],
    ocrWarnings: [],
    analogsCount: 12,
    anomalies: [],
    history: [
      {
        auction_date: '28.05.2026',
        auction_house: 'ARAI Bayside',
        auction_strictness: 0.88,
        lot_number: '6721',
        overall_grade: '4.5',
        mileage_km: 44000,
        defects_summary: 'A1 переднее правое крыло',
        closing_price_jpy: 1850000,
        sheet_archive_url: null,
      },
    ],
    hasCriticalAnomaly: false,
  },
}

function escapeXml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
}

/**
 * Builds an inline SVG auction sheet scan preview so Lightbox works offline in mock mode.
 */
function buildMockSheetSvgDataUrl(summary: LotSummary, sheet: NormalizedSheet): string {
  const title = escapeXml(`${summary.auction_house} #${summary.lot_number}`)
  const carName = escapeXml(`${summary.make} ${summary.model}`)
  const frame = escapeXml(summary.frame_id)
  const grade = escapeXml(summary.overall_grade)
  const mileage = escapeXml(
    summary.mileage_km ? `${summary.mileage_km.toLocaleString('ru-RU')} km` : '—',
  )
  const defectsText = escapeXml(
    sheet.defects.map((defect) => `${defect.panel_id}:${defect.raw_code}`).join('  ·  ') ||
      'NO MAJOR DEFECTS',
  )

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="900" height="1220" viewBox="0 0 900 1220">
    <rect width="900" height="1220" fill="#F8F6EE"/>
    <rect x="34" y="34" width="832" height="1152" rx="12" fill="#FFFDF7" stroke="#22252A" stroke-width="3"/>
    <rect x="34" y="34" width="832" height="106" fill="#1F242D"/>
    <text x="64" y="88" font-family="ui-monospace, monospace" font-size="30" font-weight="700" fill="#FFFFFF">${title}</text>
    <text x="64" y="122" font-family="system-ui, sans-serif" font-size="18" fill="#D1D5DB">JAPANESE AUCTION INSPECTION SHEET · ${frame}</text>
    <rect x="726" y="48" width="114" height="78" rx="10" fill="#FF6B00"/>
    <text x="783" y="74" text-anchor="middle" font-family="system-ui, sans-serif" font-size="14" font-weight="700" fill="#FFF7ED">GRADE</text>
    <text x="783" y="114" text-anchor="middle" font-family="ui-monospace, monospace" font-size="38" font-weight="700" fill="#FFFFFF">${grade}</text>

    <rect x="64" y="168" width="772" height="148" rx="8" fill="#FFFFFF" stroke="#D1D5DB" stroke-width="2"/>
    <line x1="450" y1="168" x2="450" y2="316" stroke="#D1D5DB" stroke-width="2"/>
    <line x1="64" y1="242" x2="836" y2="242" stroke="#D1D5DB" stroke-width="2"/>
    <text x="84" y="196" font-family="system-ui, sans-serif" font-size="14" fill="#6B7280">MODEL / 車名</text>
    <text x="84" y="226" font-family="system-ui, sans-serif" font-size="24" font-weight="700" fill="#111827">${carName}</text>
    <text x="470" y="196" font-family="system-ui, sans-serif" font-size="14" fill="#6B7280">CHASSIS / 車台番号</text>
    <text x="470" y="226" font-family="ui-monospace, monospace" font-size="22" font-weight="700" fill="#111827">${frame}</text>
    <text x="84" y="270" font-family="system-ui, sans-serif" font-size="14" fill="#6B7280">ODOMETER / 走行距離</text>
    <text x="84" y="300" font-family="ui-monospace, monospace" font-size="22" font-weight="700" fill="#111827">${mileage}</text>
    <text x="470" y="270" font-family="system-ui, sans-serif" font-size="14" fill="#6B7280">ENGINE &amp; YEAR / 排気量</text>
    <text x="470" y="300" font-family="ui-monospace, monospace" font-size="22" font-weight="700" fill="#111827">${summary.year ?? '—'} · ${summary.engine_cc ?? '—'} cc</text>

    <rect x="64" y="346" width="772" height="390" rx="8" fill="#FFFFFF" stroke="#D1D5DB" stroke-width="2"/>
    <text x="84" y="382" font-family="system-ui, sans-serif" font-size="16" font-weight="700" fill="#374151">EXTERIOR BODY DIAGRAM / 展開図</text>
    <rect x="240" y="420" width="420" height="230" rx="46" fill="#F3F4F6" stroke="#4B5563" stroke-width="3"/>
    <rect x="330" y="458" width="240" height="154" rx="18" fill="#E5E7EB" stroke="#6B7280" stroke-width="2"/>
    <line x1="330" y1="535" x2="570" y2="535" stroke="#9CA3AF" stroke-width="1.5" stroke-dasharray="6 4"/>
    <text x="450" y="698" text-anchor="middle" font-family="ui-monospace, monospace" font-size="15" fill="#4B5563">${defectsText}</text>

    <rect x="64" y="766" width="772" height="384" rx="8" fill="#FFFFFF" stroke="#D1D5DB" stroke-width="2"/>
    <text x="84" y="804" font-family="system-ui, sans-serif" font-size="16" font-weight="700" fill="#374151">INSPECTOR NOTES / 注意事項</text>
    <text x="84" y="852" font-family="ui-monospace, monospace" font-size="20" fill="#111827">• ${escapeXml(sheet.inspector_notes_raw[0] ?? '外装小キズ・補修跡')}</text>
    <text x="84" y="896" font-family="ui-monospace, monospace" font-size="20" fill="#111827">• ${escapeXml(sheet.inspector_notes_raw[1] ?? '機関・電装チェック済み')}</text>
    <text x="84" y="946" font-family="system-ui, sans-serif" font-size="18" fill="#4B5563">YUZU OCR VERIFIED · STRICTNESS ${sheet.auction_strictness_index.toFixed(2)}</text>
    <text x="84" y="1116" font-family="ui-monospace, monospace" font-size="15" fill="#9CA3AF">MOCK SCAN PREVIEW FOR ${frame}</text>
  </svg>`

  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
}

function buildWiseSteps(params: {
  bidJpy: number
  bidRub: number
  japanFeeJpy: number
  japanFeeRub: number
  freightRub: number
  customsDutyEur: number
  customsDutyRub: number
  utilFeeRub: number
  brokerAndSvhRub: number
  repairRub: number
  includeRepairs: boolean
}): WiseCostStep[] {
  const steps: WiseCostStep[] = [
    {
      step_number: 1,
      name_ru: 'Ставка на аукционе (FOB Япония)',
      amount_rub: params.bidRub,
      original_currency: 'JPY',
      original_amount: params.bidJpy,
      is_optional: false,
    },
    {
      step_number: 2,
      name_ru: 'Аукционный сбор и логистика по Японии',
      amount_rub: params.japanFeeRub,
      original_currency: 'JPY',
      original_amount: params.japanFeeJpy,
      is_optional: false,
    },
    {
      step_number: 3,
      name_ru: 'Морской фрахт в порт Владивосток',
      amount_rub: params.freightRub,
      original_currency: null,
      original_amount: null,
      is_optional: false,
    },
    {
      step_number: 4,
      name_ru: 'Таможенная пошлина ЕАЭС',
      amount_rub: params.customsDutyRub,
      original_currency: 'EUR',
      original_amount: params.customsDutyEur,
      is_optional: false,
    },
    {
      step_number: 5,
      name_ru: 'Утилизационный сбор РФ (ПП РФ № 1713)',
      amount_rub: params.utilFeeRub,
      original_currency: null,
      original_amount: null,
      is_optional: false,
    },
    {
      step_number: 6,
      name_ru: 'СВХ, таможенный брокер, СБКТС и ЭПТС',
      amount_rub: params.brokerAndSvhRub,
      original_currency: null,
      original_amount: null,
      is_optional: false,
    },
    {
      step_number: 7,
      name_ru: 'Смета кузовного ремонта Farpost',
      amount_rub: params.includeRepairs ? params.repairRub : 0,
      original_currency: null,
      original_amount: null,
      is_optional: true,
    },
  ]
  return steps
}

function deriveVerdict(params: {
  netBenefitRub: number
  benefitPct: number
  riskFlags: RiskFlags
  hasCriticalAnomaly: boolean
  metiRisk: boolean
  isCommercialUtil: boolean
  baseBodySummary: string
  baseInteriorSummary: string
  baseBullets: string[]
}): TrafficLightVerdict {
  const hasStopFactor =
    params.hasCriticalAnomaly ||
    params.riskFlags.is_flooded ||
    params.riskFlags.airbag_deployed ||
    params.riskFlags.pillar_or_frame_repair ||
    params.riskFlags.repaired_grade_r_ra ||
    params.riskFlags.odometer_issue

  let verdict: TrafficLightColor = 'yellow'
  let headline = 'ПОД ВОПРОСОМ — НУЖНА ПРОВЕРКА'

  if (hasStopFactor || params.netBenefitRub < 50_000) {
    verdict = 'red'
    headline = hasStopFactor
      ? 'ВЫСОКИЙ РИСК — ПОКУПКА НЕ РЕКОМЕНДОВАНА'
      : 'НИЗКАЯ ВЫГОДА — СТАВКА НЕВЫГОДНА'
  } else if (
    params.netBenefitRub >= 150_000 &&
    !params.riskFlags.underbody_rust &&
    !params.isCommercialUtil
  ) {
    verdict = 'green'
    headline = 'РЕКОМЕНДОВАНО К ПОКУПКЕ'
  } else if (params.netBenefitRub >= 150_000) {
    verdict = 'yellow'
    headline = 'ПОД ВОПРОСОМ — УЧТИТЕ НЮАНСЫ'
  } else {
    verdict = 'yellow'
    headline = 'СДЕРЖАННАЯ ВЫГОДА — СЛЕДИТЕ ЗА СТАВКОЙ'
  }

  const badgeText =
    params.netBenefitRub >= 0
      ? `Выгода: ${formatRub(params.netBenefitRub, { signed: true })}`
      : `Переплата: ${formatRub(Math.abs(params.netBenefitRub))}`

  const shortPrefix =
    verdict === 'green' ? 'Можно брать' : verdict === 'yellow' ? 'Под вопросом' : 'Высокий риск'

  const bullets = [...params.baseBullets]
  if (params.metiRisk && !bullets.some((item) => item.includes('METI'))) {
    bullets.push('Автомобиль попадает под ограничения METI — нужна транзитная логистика')
  }
  if (params.isCommercialUtil) {
    bullets.push('В расчёт заложен коммерческий утильсбор (ПП РФ № 1255)')
  }

  return {
    verdict,
    headline,
    short_verdict_label: `${shortPrefix} • ${formatRub(params.netBenefitRub, { signed: true })}`,
    badge_text: badgeText,
    net_benefit_rub: params.netBenefitRub,
    benefit_percentage: Number(params.benefitPct.toFixed(1)),
    body_summary_ru: params.baseBodySummary,
    interior_summary_ru: params.baseInteriorSummary,
    reasoning_bullets: bullets,
  }
}

function buildSafetyChecklist(riskFlags: RiskFlags): SafetyChecklist {
  const frameStatus: ChecklistItemStatus = riskFlags.pillar_or_frame_repair ? 'critical' : 'ok'
  const srsStatus: ChecklistItemStatus = riskFlags.airbag_deployed ? 'critical' : 'ok'
  const engineStatus: ChecklistItemStatus = riskFlags.odometer_issue ? 'critical' : 'ok'
  const corrosionStatus: ChecklistItemStatus = riskFlags.underbody_corrosion
    ? 'critical'
    : riskFlags.underbody_rust
      ? 'warning'
      : 'ok'
  const floodStatus: ChecklistItemStatus =
    riskFlags.is_flooded || riskFlags.hail_damage ? 'critical' : 'ok'

  const items: SafetyCheckItem[] = [
    {
      system_key: 'structural_frame',
      label_ru: 'Силовой каркас и лонжероны',
      status: frameStatus,
      detail_ru: riskFlags.pillar_or_frame_repair
        ? 'На листе выявлены следы ремонта несущих стоек или лонжеронов (оценка R/RA).'
        : 'Следов ремонта лонжеронов, стоек и пола багажника не выявлено.',
    },
    {
      system_key: 'airbags_srs',
      label_ru: 'Подушки безопасности (SRS)',
      status: srsStatus,
      detail_ru: riskFlags.airbag_deployed
        ? 'Зафиксировано срабатывание или демонтаж подушек безопасности.'
        : 'Замечаний по модулям SRS и индикаторам на приборной панели нет.',
    },
    {
      system_key: 'engine_transmission',
      label_ru: 'Двигатель, КПП и одометр',
      status: engineStatus,
      detail_ru: riskFlags.odometer_issue
        ? 'Обнаружена нестыковка пробега с архивными торгами или замена одометра.'
        : 'Пробег подтверждён, посторонних шумов и ошибок трансмиссии не отмечено.',
    },
    {
      system_key: 'underbody_corrosion',
      label_ru: 'Днище, пороги и коррозия',
      status: corrosionStatus,
      detail_ru: riskFlags.underbody_corrosion
        ? 'Глубокая/сквозная коррозия порогов и элементов рамы.'
        : riskFlags.underbody_rust
          ? 'Поверхностный налёт ржавчины S1/S2 — рекомендуется антикор во Владивостоке.'
          : 'Критичной коррозии силовых элементов и днища не обнаружено.',
    },
    {
      system_key: 'flood_or_fire',
      label_ru: 'Признаки затопления / градобоя',
      status: floodStatus,
      detail_ru: riskFlags.is_flooded
        ? 'На аукционном листе присутствуют отметки топляка (冠水車).'
        : 'Признаков подтопления салона, окисления проводки или градобоя нет.',
    },
  ]

  const hasCritical = items.some((item) => item.status === 'critical')
  const hasWarning = items.some((item) => item.status === 'warning')
  const overallStatus: ChecklistItemStatus = hasCritical
    ? 'critical'
    : hasWarning
      ? 'warning'
      : 'ok'
  const overallLabel = hasCritical ? 'Стоп-фактор' : hasWarning ? 'Есть замечания' : 'В норме'

  return {
    overall_status: overallStatus,
    overall_label_ru: overallLabel,
    items,
  }
}

export function buildMockLotDetail(summary: LotSummary): LotDetailResponse {
  const preset = PRESET_CONFIGS[summary.lot_id]
  const riskFlags: RiskFlags = {
    ...DEFAULT_RISK_FLAGS,
    repaired_grade_r_ra: summary.overall_grade === 'R' || summary.overall_grade === 'RA',
    ...preset?.riskFlagsOverride,
  }

  const partsTotal = preset
    ? preset.parts.reduce((acc, part) => acc + part.price_from_rub, 0)
    : summary.has_anomaly
      ? 15000
      : 0
  const worksTotal = preset
    ? preset.serviceWorks.reduce((acc, work) => acc + work.amount_rub, 0)
    : summary.has_anomaly
      ? 9000
      : 0
  const repairTotal = partsTotal + worksTotal

  const farpostRepair: FarpostRepairSummary = {
    parts: preset?.parts ?? [],
    service_works:
      preset?.serviceWorks ??
      (repairTotal > 0
        ? [
            {
              work_type: 'pdr_and_polish',
              label_ru: 'Предпродажная подготовка и устранение косметики',
              amount_rub: repairTotal,
              zero_cost_reason_ru: null,
            },
          ]
        : []),
    total_parts_from_rub: partsTotal,
    total_works_rub: worksTotal,
    grand_total_repair_rub: repairTotal,
    has_color_matched_parts: Boolean(preset?.serviceWorks.some((w) => w.amount_rub === 0)),
    included_in_turnkey_hint_ru: 'Сумма уже включена в расчёт под ключ во Владивостоке',
  }

  const engineCc = summary.engine_cc ?? 1496
  const powerHp = preset?.powerHp ?? (engineCc > 1900 ? 185 : 122)
  const isUnder160 = powerHp <= 160
  const isCommercialUtil = preset?.isCommercialUtilDefault ?? !isUnder160

  const freightRub = summary.meti_sanction_risk ? 155_000 : 95_000
  const japanFeeJpy = 85_000
  const japanFeeRub = Math.round(japanFeeJpy * JPY_RUB_RATE)
  const dutyRateEurPerCc =
    engineCc <= 1500 ? 1.7 : engineCc <= 1800 ? 2.5 : engineCc <= 2300 ? 2.7 : 3.0
  const customsDutyEur = Number((engineCc * dutyRateEurPerCc).toFixed(2))
  const customsDutyRub = Math.round(customsDutyEur * EUR_RUB_RATE)
  const utilFeeRub = isCommercialUtil ? COMMERCIAL_UTIL_FEE_RUB : PERSONAL_UTIL_FEE_RUB
  const brokerAndSvhRub = 48_000

  const fixedCostsRub =
    japanFeeRub + freightRub + customsDutyRub + utilFeeRub + brokerAndSvhRub + repairTotal
  const rawBidRub = Math.max(220_000, summary.turnkey_cost_rub - fixedCostsRub)
  const carBidJpy = Math.max(300_000, Math.round(rawBidRub / JPY_RUB_RATE / 10_000) * 10_000)
  const carBidRub = Math.max(0, summary.turnkey_cost_rub - fixedCostsRub)

  const steps = buildWiseSteps({
    bidJpy: carBidJpy,
    bidRub: carBidRub,
    japanFeeJpy,
    japanFeeRub,
    freightRub,
    customsDutyEur,
    customsDutyRub,
    utilFeeRub,
    brokerAndSvhRub,
    repairRub: repairTotal,
    includeRepairs: true,
  })

  const benefitPct =
    summary.turnkey_cost_rub > 0 ? (summary.net_benefit_rub / summary.turnkey_cost_rub) * 100 : 0

  const defects: NormalizedDefect[] = preset?.defects ?? [
    {
      panel_id: 'front_bumper',
      panel_ru: PANEL_LABELS_RU.front_bumper,
      defect_types: ['A'],
      severity: 1,
      raw_code: 'A1',
      description_ru: 'Передний бампер — незначительная царапина по лаку',
    },
  ]

  const passport: NormalizedSheet = {
    lot_number: summary.lot_number,
    auction_house: summary.auction_house,
    auction_branch: preset?.auctionBranch ?? `${summary.auction_house} Japan`,
    auction_strictness_index: preset?.strictness ?? 0.8,
    make: summary.make,
    model: summary.model,
    trim: preset?.trim ?? null,
    model_code: preset?.modelCode ?? `${summary.frame_id.split('-')[0] ?? 'JDM'}`,
    chassis_number: summary.frame_id,
    frame_id: summary.frame_id,
    frame_id_confidence: 'exact',
    first_reg_year: summary.year,
    first_reg_month: 6,
    first_reg_date_str: summary.year ? `06.${summary.year} (3–5 лет, ЕАЭС)` : null,
    is_pass_corridor_3_5: true,
    engine_cc: engineCc,
    power_hp: powerHp,
    power_hp_source: 'drom_catalog',
    is_under_160_hp: isUnder160,
    mileage_km: summary.mileage_km,
    odometer_status: riskFlags.odometer_issue ? 'tampered' : 'confirmed',
    transmission: preset?.transmission ?? 'Вариатор (CVT)',
    drive_type: preset?.driveType ?? '2WD',
    fuel_type: preset?.fuelType ?? 'gasoline',
    color_ru: preset?.colorRu ?? 'Белый перламутр',
    paint_code: preset?.paintCode ?? '070',
    overall_grade: summary.overall_grade,
    exterior_grade: preset?.exteriorGrade ?? 'B',
    interior_grade: preset?.interiorGrade ?? 'B',
    shaken_until: preset?.shakenUntil ?? null,
    recycling_fee_yen: preset?.recyclingYen ?? 10800,
    recycling_fee_paid: true,
    equipment_ru: preset?.equipment ?? [
      'Климат-контроль',
      'Камера заднего вида',
      'Бесключевой доступ',
    ],
    defects,
    risk_flags: riskFlags,
    inspector_notes_ru: preset?.inspectorNotesRu ?? [
      'Кузов и оптика соответствуют заявленной оценке аукционного листа',
      'Двигатель и трансмиссия без замечаний по холодному пуску',
    ],
    inspector_notes_raw: preset?.inspectorNotesRaw ?? ['外装小キズ', '機関良好'],
    seller_comments_ru: preset?.sellerCommentsRu ?? ['Один владелец в Японии'],
    extra_ru: ['Два комплекта ключей'],
    ocr_warnings: preset?.ocrWarnings ?? [],
    low_confidence_fields: [],
  }

  const verdict: TrafficLightVerdict = {
    verdict: summary.verdict,
    headline:
      summary.verdict === 'green'
        ? 'РЕКОМЕНДОВАНО К ПОКУПКЕ'
        : summary.verdict === 'yellow'
          ? 'ПОД ВОПРОСОМ — ТРЕБУЕТ ВНИМАНИЯ'
          : 'ВЫСОКИЙ РИСК — ПОКУПКА НЕ РЕКОМЕНДОВАНА',
    short_verdict_label: summary.verdict_headline,
    badge_text:
      summary.net_benefit_rub >= 0
        ? `Выгода: ${formatRub(summary.net_benefit_rub, { signed: true })}`
        : `Переплата: ${formatRub(Math.abs(summary.net_benefit_rub))}`,
    net_benefit_rub: summary.net_benefit_rub,
    benefit_percentage: Number(benefitPct.toFixed(1)),
    body_summary_ru:
      preset?.bodySummaryRu ??
      (summary.anomaly_text || 'Силовая структура без нареканий, мелкие эксплуатационные отметки'),
    interior_summary_ru:
      preset?.interiorSummaryRu ??
      `Оценка салона ${passport.interior_grade ?? 'B'} — ухоженное состояние`,
    reasoning_bullets: preset?.reasoningBullets ?? [
      `Лист площадки ${summary.auction_house} (индекс строгости ${passport.auction_strictness_index.toFixed(2)})`,
      `Пробег ${summary.mileage_km ? `${summary.mileage_km.toLocaleString('ru-RU')} км` : '—'} подтверждён`,
    ],
  }

  const customs: CustomsCalculation = {
    age_corridor: '3_to_5_years',
    duty_calculation_mode: 'eur_per_cc',
    engine_cc: engineCc,
    duty_rate_eur_per_cc: dutyRateEurPerCc,
    effective_duty_pct: null,
    customs_duty_eur: customsDutyEur,
    customs_duty_rub: customsDutyRub,
    is_under_160_hp: isUnder160,
    is_commercial_util: isCommercialUtil,
    utilization_fee_rub: utilFeeRub,
    customs_clearance_fee_rub: 4268,
    freight_vladivostok_rub: freightRub,
    broker_svh_sbkts_rub: brokerAndSvhRub,
    meti_sanction_risk: summary.meti_sanction_risk,
    rates_snapshot: {
      jpy_rub_bank: JPY_RUB_RATE,
      jpy_rate_source: 'VL.ru Деньги',
      eur_rub_cbrf: EUR_RUB_RATE,
      usd_rub_cbrf: USD_RUB_RATE,
      cbrf_date: '13.11.2026',
    },
  }

  const economics: EconomicsDetail = {
    bid_slider_min_jpy: Math.max(200_000, Math.round((carBidJpy * 0.55) / 10_000) * 10_000),
    bid_slider_max_jpy: Math.max(
      carBidJpy + 500_000,
      Math.round((carBidJpy * 1.65) / 10_000) * 10_000,
    ),
    bid_slider_step_jpy: 10_000,
    is_repairs_included: true,
    customs,
    farpost_repair: farpostRepair,
    wise_cost_ladder: {
      car_bid_jpy: carBidJpy,
      car_bid_rub: carBidRub,
      turnkey_cost_rub: summary.turnkey_cost_rub,
      market_price_rf_rub: summary.market_price_rf_rub,
      net_benefit_rub: summary.net_benefit_rub,
      benefit_percentage: Number(benefitPct.toFixed(1)),
      steps,
    },
  }

  const hasCriticalAnomaly = preset?.hasCriticalAnomaly ?? false
  const anomalies = preset?.anomalies ?? []
  const history = preset?.history ?? [
    {
      auction_date: '25.05.2026',
      auction_house: passport.auction_branch ?? summary.auction_house,
      auction_strictness: passport.auction_strictness_index,
      lot_number: summary.lot_number,
      overall_grade: summary.overall_grade,
      mileage_km: summary.mileage_km,
      defects_summary: defects.map((d) => `${d.raw_code} ${d.panel_ru}`).join(', '),
      closing_price_jpy: carBidJpy,
      sheet_archive_url: null,
    },
  ]

  const audit: CrossAuditReport = {
    status: hasCriticalAnomaly || anomalies.length > 0 ? 'anomaly_detected' : 'clean',
    source_name: 'AucJP + AAA Japan / Pravto',
    is_archive_available: true,
    risk_level: hasCriticalAnomaly ? 'CRITICAL' : anomalies.length > 0 ? 'WARNING' : 'CLEAN',
    has_critical_anomaly: hasCriticalAnomaly,
    headline_ru: hasCriticalAnomaly
      ? 'ВНИМАНИЕ: Выявлены расхождения пробега и следы силового ремонта в архиве торгов'
      : anomalies.length > 0
        ? 'Зафиксированы расхождения кузовных деталей относительно прошлых торгов'
        : 'Кросс-аудит чист — расхождений с историей японских аукционов не найдено',
    times_auctioned: history.length,
    verified_at: '2026-11-13T10:15:00Z',
    anomalies,
    history,
  }

  const sheetDataUrl = buildMockSheetSvgDataUrl(summary, passport)
  const dromQuery = encodeURIComponent(`${summary.make} ${summary.model}`)

  return {
    lot_id: summary.lot_id,
    created_at: summary.created_at,
    updated_at: '2026-11-13T10:15:00Z',
    passport,
    verdict,
    market: {
      market_price_rf_rub: summary.market_price_rf_rub,
      analogs_count: preset?.analogsCount ?? 10,
      price_min_rub: Math.round(summary.market_price_rf_rub * 0.89),
      price_max_rub: Math.round(summary.market_price_rf_rub * 1.12),
      search_region_ru: 'ДФО / Владивосток',
      excludes_under_order: true,
      filtered_out_under_order_count: 5,
      is_fallback: false,
      fallback_reason_ru: null,
      drom_search_url: `https://auto.drom.ru/all/?q=${dromQuery}`,
    },
    audit,
    safety_checklist: buildSafetyChecklist(riskFlags),
    economics,
    media: {
      sheet_thumbnail_url: summary.thumbnail_url ?? sheetDataUrl,
      sheet_scan_url: sheetDataUrl,
      drom_search_url: `https://auto.drom.ru/all/?q=${dromQuery}`,
    },
  }
}

export function recalculateMockLotDetail(
  base: LotDetailResponse,
  payload: RecalculateRequest,
): RecalculateResponse {
  const rate = base.economics.customs.rates_snapshot.jpy_rub_bank || JPY_RUB_RATE
  const appliedBidJpy =
    typeof payload.bid_jpy === 'number'
      ? Math.round(payload.bid_jpy)
      : typeof payload.bid_rub === 'number'
        ? Math.round(payload.bid_rub / rate)
        : base.economics.wise_cost_ladder.car_bid_jpy

  const appliedBidRub =
    typeof payload.bid_rub === 'number'
      ? Math.round(payload.bid_rub)
      : Math.round(appliedBidJpy * rate)

  const isCommercialUtil =
    typeof payload.is_commercial_util === 'boolean'
      ? payload.is_commercial_util
      : base.economics.customs.is_commercial_util

  const includeRepairs =
    typeof payload.include_repairs === 'boolean'
      ? payload.include_repairs
      : base.economics.is_repairs_included

  const utilFeeRub = isCommercialUtil ? COMMERCIAL_UTIL_FEE_RUB : PERSONAL_UTIL_FEE_RUB
  const freightRub = payload.custom_freight_rub ?? base.economics.customs.freight_vladivostok_rub
  const japanFeeStep = base.economics.wise_cost_ladder.steps.find((s) => s.step_number === 2)
  const japanFeeJpy = japanFeeStep?.original_amount ?? 85_000
  const japanFeeRub = japanFeeStep?.amount_rub ?? Math.round(japanFeeJpy * rate)
  const customsDutyEur = base.economics.customs.customs_duty_eur
  const customsDutyRub = base.economics.customs.customs_duty_rub
  const brokerAndSvhRub = base.economics.customs.broker_svh_sbkts_rub
  const repairRub = base.economics.farpost_repair.grand_total_repair_rub

  const updatedSteps = buildWiseSteps({
    bidJpy: appliedBidJpy,
    bidRub: appliedBidRub,
    japanFeeJpy,
    japanFeeRub,
    freightRub,
    customsDutyEur,
    customsDutyRub,
    utilFeeRub,
    brokerAndSvhRub,
    repairRub,
    includeRepairs,
  })

  const turnkeyCostRub = updatedSteps.reduce((acc, step) => acc + step.amount_rub, 0)
  const marketPriceRfRub = base.market.market_price_rf_rub
  const netBenefitRub = marketPriceRfRub - turnkeyCostRub
  const benefitPct = turnkeyCostRub > 0 ? (netBenefitRub / turnkeyCostRub) * 100 : 0

  const updatedCustoms: CustomsCalculation = {
    ...base.economics.customs,
    is_commercial_util: isCommercialUtil,
    utilization_fee_rub: utilFeeRub,
    freight_vladivostok_rub: freightRub,
  }

  const updatedVerdict = deriveVerdict({
    netBenefitRub,
    benefitPct,
    riskFlags: base.passport.risk_flags,
    hasCriticalAnomaly: base.audit.has_critical_anomaly,
    metiRisk: base.economics.customs.meti_sanction_risk,
    isCommercialUtil,
    baseBodySummary: base.verdict.body_summary_ru,
    baseInteriorSummary: base.verdict.interior_summary_ru,
    baseBullets: base.verdict.reasoning_bullets,
  })

  return {
    lot_id: base.lot_id,
    recalculated_at: new Date().toISOString(),
    applied_bid_jpy: appliedBidJpy,
    applied_bid_rub: appliedBidRub,
    is_commercial_util: isCommercialUtil,
    include_repairs: includeRepairs,
    customs: updatedCustoms,
    wise_cost_ladder: {
      car_bid_jpy: appliedBidJpy,
      car_bid_rub: appliedBidRub,
      turnkey_cost_rub: turnkeyCostRub,
      market_price_rf_rub: marketPriceRfRub,
      net_benefit_rub: netBenefitRub,
      benefit_percentage: Number(benefitPct.toFixed(1)),
      steps: updatedSteps,
    },
    turnkey_cost_rub: turnkeyCostRub,
    market_price_rf_rub: marketPriceRfRub,
    net_benefit_rub: netBenefitRub,
    benefit_percentage: Number(benefitPct.toFixed(1)),
    verdict: updatedVerdict,
    pdf_report_stale: true,
  }
}
