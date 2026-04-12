import type { Direction, Goal, SubGoal, Task, Step } from '../types'

function id(prefix: string, n: number | string) {
  return `${prefix}_${n}`
}

// ─── DIRECTIONS ────────────────────────────────────────────────────────────
export const DIRECTIONS: Direction[] = [
  { id: 'dir_analytics',     name: 'Аналитика',      goalId: 'goal_analytics' },
  { id: 'dir_finance',       name: 'Финансы',         goalId: 'goal_finance' },
  { id: 'dir_ai',            name: 'AI',              goalId: 'goal_ai' },
  { id: 'dir_sales',         name: 'Продажи',         goalId: 'goal_sales' },
  { id: 'dir_infra',         name: 'Инфраструктура',  goalId: 'goal_infra' },
]

// ─── GOALS ─────────────────────────────────────────────────────────────────
export const GOALS: Goal[] = [
  { id: 'goal_analytics', title: 'Построить систему принятия решений на основе данных',          directionId: 'dir_analytics' },
  { id: 'goal_finance',   title: 'Достичь операционной безубыточности к Q3 2026',                directionId: 'dir_finance' },
  { id: 'goal_ai',        title: 'Запустить AI-продукт с первыми платящими пользователями',      directionId: 'dir_ai' },
  { id: 'goal_sales',     title: 'Выйти на 50 активных клиентов до конца года',                  directionId: 'dir_sales' },
  { id: 'goal_infra',     title: 'Перевести все сервисы на production-grade инфраструктуру',     directionId: 'dir_infra' },
]

// ─── SUBGOALS ───────────────────────────────────────────────────────────────
export const SUBGOALS: SubGoal[] = [
  // Analytics
  { id: 'sg_a1', title: 'Data pipeline',          goalId: 'goal_analytics', directionId: 'dir_analytics', order: 0, taskIds: ['t_a1', 't_a2'] },
  { id: 'sg_a2', title: 'Дашборды и метрики',     goalId: 'goal_analytics', directionId: 'dir_analytics', order: 1, taskIds: ['t_a3', 't_a4'] },
  { id: 'sg_a3', title: 'Аналитические отчёты',   goalId: 'goal_analytics', directionId: 'dir_analytics', order: 2, taskIds: ['t_a5'] },

  // Finance
  { id: 'sg_f1', title: 'Учёт расходов',           goalId: 'goal_finance', directionId: 'dir_finance', order: 0, taskIds: ['t_f1', 't_f2'] },
  { id: 'sg_f2', title: 'Прогноз cash flow',        goalId: 'goal_finance', directionId: 'dir_finance', order: 1, taskIds: ['t_f3'] },
  { id: 'sg_f3', title: 'Инвестиционный раунд',     goalId: 'goal_finance', directionId: 'dir_finance', order: 2, taskIds: ['t_f4', 't_f5'] },

  // AI
  { id: 'sg_ai1', title: 'MVP модели',             goalId: 'goal_ai', directionId: 'dir_ai', order: 0, taskIds: ['t_ai1', 't_ai2'] },
  { id: 'sg_ai2', title: 'Продуктовая обёртка',    goalId: 'goal_ai', directionId: 'dir_ai', order: 1, taskIds: ['t_ai3', 't_ai4'] },
  { id: 'sg_ai3', title: 'Первые пользователи',    goalId: 'goal_ai', directionId: 'dir_ai', order: 2, taskIds: ['t_ai5'] },

  // Sales
  { id: 'sg_s1', title: 'ICP и позиционирование',  goalId: 'goal_sales', directionId: 'dir_sales', order: 0, taskIds: ['t_s1', 't_s2'] },
  { id: 'sg_s2', title: 'Outreach pipeline',        goalId: 'goal_sales', directionId: 'dir_sales', order: 1, taskIds: ['t_s3', 't_s4'] },
  { id: 'sg_s3', title: 'Закрытие сделок',          goalId: 'goal_sales', directionId: 'dir_sales', order: 2, taskIds: ['t_s5'] },

  // Infra
  { id: 'sg_i1', title: 'CI/CD и деплой',          goalId: 'goal_infra', directionId: 'dir_infra', order: 0, taskIds: ['t_i1', 't_i2'] },
  { id: 'sg_i2', title: 'Мониторинг и алерты',      goalId: 'goal_infra', directionId: 'dir_infra', order: 1, taskIds: ['t_i3', 't_i4'] },
  { id: 'sg_i3', title: 'Безопасность',             goalId: 'goal_infra', directionId: 'dir_infra', order: 2, taskIds: ['t_i5'] },
]

// ─── STEPS ──────────────────────────────────────────────────────────────────
function steps(taskId: string, titles: string[]): Step[] {
  return titles.map((title, i) => ({
    id: `${taskId}_s${i}`,
    title,
    taskId,
    completed: i === 0 && titles.length > 1,
    order: i,
  }))
}

// ─── TASKS ──────────────────────────────────────────────────────────────────
export const TASKS: Task[] = [
  // Analytics
  {
    id: 't_a1', title: 'Настроить ETL-пайплайн из PostgreSQL в ClickHouse',
    subGoalId: 'sg_a1', directionId: 'dir_analytics', status: 'active',
    deadline: '2026-04-20', totalTime: 5400, createdAt: '2026-03-15',
    steps: steps('t_a1', [
      'Поднять ClickHouse на staging',
      'Написать Airbyte connector для postgres',
      'Настроить расписание синхронизации 1h',
      'Проверить консистентность данных',
      'Задокументировать схему',
    ]),
  },
  {
    id: 't_a2', title: 'Реализовать инкрементальную загрузку событий',
    subGoalId: 'sg_a1', directionId: 'dir_analytics', status: 'stuck',
    deadline: '2026-04-15', totalTime: 3600, createdAt: '2026-03-20',
    steps: steps('t_a2', [
      'Определить watermark-поле для каждой таблицы',
      'Реализовать cursor-based загрузку',
      'Добавить deduplication логику',
    ]),
  },
  {
    id: 't_a3', title: 'Построить дашборд по unit-экономике',
    subGoalId: 'sg_a2', directionId: 'dir_analytics', status: 'active',
    deadline: '2026-04-28', totalTime: 7200, createdAt: '2026-03-25',
    steps: steps('t_a3', [
      'Согласовать метрики с CEO',
      'Написать SQL-запросы для CAC, LTV, MRR',
      'Собрать дашборд в Metabase',
      'Добавить автообновление каждые 6h',
    ]),
  },
  {
    id: 't_a4', title: 'Алерты на аномалии в ключевых метриках',
    subGoalId: 'sg_a2', directionId: 'dir_analytics', status: 'inbox',
    totalTime: 0, createdAt: '2026-04-01',
    steps: steps('t_a4', [
      'Определить пороги для алертов',
      'Настроить Grafana alerts',
      'Подключить Slack-уведомления',
    ]),
  },
  {
    id: 't_a5', title: 'Еженедельный аналитический отчёт для команды',
    subGoalId: 'sg_a3', directionId: 'dir_analytics', status: 'no-next-step',
    totalTime: 1800, createdAt: '2026-03-28',
    steps: [],
  },

  // Finance
  {
    id: 't_f1', title: 'Перенести все расходы в единую таблицу',
    subGoalId: 'sg_f1', directionId: 'dir_finance', status: 'completed',
    deadline: '2026-03-31', totalTime: 4320, createdAt: '2026-03-10',
    steps: steps('t_f1', [
      'Собрать выписки из 3 банков',
      'Категоризировать расходы',
      'Загрузить в Google Sheets',
      'Создать сводную таблицу',
    ]).map(s => ({ ...s, completed: true })),
  },
  {
    id: 't_f2', title: 'Настроить автоматический учёт через API банка',
    subGoalId: 'sg_f1', directionId: 'dir_finance', status: 'active',
    deadline: '2026-04-25', totalTime: 2700, createdAt: '2026-03-18',
    steps: steps('t_f2', [
      'Подключить Tinkoff Open API',
      'Парсить транзакции ежедневно',
      'Обогащать категориями через GPT',
      'Выгружать в таблицу учёта',
    ]),
  },
  {
    id: 't_f3', title: 'Модель прогноза cash flow на 3 месяца',
    subGoalId: 'sg_f2', directionId: 'dir_finance', status: 'active',
    deadline: '2026-05-01', totalTime: 3600, createdAt: '2026-03-22',
    steps: steps('t_f3', [
      'Определить переменные и константы',
      'Построить baseline-модель в Excel',
      'Добавить сценарный анализ',
      'Валидировать на исторических данных',
    ]),
  },
  {
    id: 't_f4', title: 'Подготовить финансовую модель для инвесторов',
    subGoalId: 'sg_f3', directionId: 'dir_finance', status: 'active',
    deadline: '2026-04-30', totalTime: 9000, createdAt: '2026-03-05',
    steps: steps('t_f4', [
      'P&L за 12 месяцев',
      'Прогноз роста выручки x3',
      'Breakdown расходов по статьям',
      'Расчёт break-even point',
      'Оформить в pitch deck формат',
    ]),
  },
  {
    id: 't_f5', title: 'Составить список потенциальных инвесторов',
    subGoalId: 'sg_f3', directionId: 'dir_finance', status: 'overdue',
    deadline: '2026-04-05', totalTime: 1200, createdAt: '2026-03-01',
    steps: steps('t_f5', [
      'Ресёрч фондов по вертикали',
      'Составить таблицу 30+ контактов',
      'Приоритизировать по теплоте',
    ]),
  },

  // AI
  {
    id: 't_ai1', title: 'Обучить fine-tuned классификатор намерений',
    subGoalId: 'sg_ai1', directionId: 'dir_ai', status: 'active',
    deadline: '2026-04-18', totalTime: 12600, createdAt: '2026-03-12',
    steps: steps('t_ai1', [
      'Разметить 500 примеров',
      'Подготовить training pipeline',
      'Запустить fine-tuning на Mistral-7B',
      'Оценить accuracy на test set',
      'Деплой на Inference endpoint',
    ]),
  },
  {
    id: 't_ai2', title: 'RAG-система по внутренней документации',
    subGoalId: 'sg_ai1', directionId: 'dir_ai', status: 'stuck',
    deadline: '2026-04-22', totalTime: 5400, createdAt: '2026-03-17',
    steps: steps('t_ai2', [
      'Собрать и нормализовать документацию',
      'Chunking + embedding через OpenAI',
      'Индексировать в Pinecone',
      'Реализовать retrieval + rerank',
      'Интегрировать в чат-интерфейс',
    ]),
  },
  {
    id: 't_ai3', title: 'Собрать web-интерфейс для демо',
    subGoalId: 'sg_ai2', directionId: 'dir_ai', status: 'active',
    deadline: '2026-04-25', totalTime: 7200, createdAt: '2026-03-20',
    steps: steps('t_ai3', [
      'Макет в Figma (2 экрана)',
      'React + Vite scaffold',
      'Chat UI компонент',
      'Подключить к API',
      'Деплой на Vercel',
    ]),
  },
  {
    id: 't_ai4', title: 'API wrapper с rate limiting и мониторингом',
    subGoalId: 'sg_ai2', directionId: 'dir_ai', status: 'inbox',
    totalTime: 0, createdAt: '2026-04-02',
    steps: steps('t_ai4', [
      'Express/Fastify endpoint',
      'Добавить auth middleware',
      'Rate limiting по API key',
      'Логировать все запросы',
    ]),
  },
  {
    id: 't_ai5', title: 'Онбординг первых 10 beta-пользователей',
    subGoalId: 'sg_ai3', directionId: 'dir_ai', status: 'inbox',
    totalTime: 0, createdAt: '2026-04-03',
    steps: steps('t_ai5', [
      'Выбрать 10 кандидатов',
      'Написать onboarding письмо',
      'Провести 30-минутные звонки',
      'Собрать feedback',
    ]),
  },

  // Sales
  {
    id: 't_s1', title: 'Описать ICP: компании, роли, боли',
    subGoalId: 'sg_s1', directionId: 'dir_sales', status: 'completed',
    deadline: '2026-03-25', totalTime: 3600, createdAt: '2026-03-01',
    steps: steps('t_s1', [
      'Провести 5 customer interviews',
      'Синтез болей и Jobs-to-be-done',
      'Написать ICP-документ',
    ]).map(s => ({ ...s, completed: true })),
  },
  {
    id: 't_s2', title: 'Обновить pitch deck под новый ICP',
    subGoalId: 'sg_s1', directionId: 'dir_sales', status: 'active',
    deadline: '2026-04-14', totalTime: 4500, createdAt: '2026-03-15',
    steps: steps('t_s2', [
      'Актуализировать problem slide',
      'Переписать value proposition',
      'Добавить social proof',
      'Обновить pricing slide',
    ]),
  },
  {
    id: 't_s3', title: 'Собрать базу лидов 200+ контактов',
    subGoalId: 'sg_s2', directionId: 'dir_sales', status: 'active',
    deadline: '2026-04-17', totalTime: 5400, createdAt: '2026-03-20',
    steps: steps('t_s3', [
      'LinkedIn scraping по ICP',
      'Верифицировать email через Hunter.io',
      'Сегментировать по теплоте',
      'Загрузить в CRM',
    ]),
  },
  {
    id: 't_s4', title: 'Запустить outreach-кампанию',
    subGoalId: 'sg_s2', directionId: 'dir_sales', status: 'overdue',
    deadline: '2026-04-08', totalTime: 2700, createdAt: '2026-03-25',
    steps: steps('t_s4', [
      'Написать 3 варианта cold email',
      'A/B тест темы письма',
      'Настроить последовательность в Lemlist',
      'Запустить первую волну 50 контактов',
    ]),
  },
  {
    id: 't_s5', title: 'Закрыть первые 5 платящих клиентов',
    subGoalId: 'sg_s3', directionId: 'dir_sales', status: 'active',
    deadline: '2026-05-15', totalTime: 8100, createdAt: '2026-03-10',
    steps: steps('t_s5', [
      'Провести demo-звонки с 10 лидами',
      'Отправить proposal + договор',
      'Follow-up после 3 дней',
      'Оформить оплату',
    ]),
  },

  // Infra
  {
    id: 't_i1', title: 'Настроить GitHub Actions CI pipeline',
    subGoalId: 'sg_i1', directionId: 'dir_infra', status: 'completed',
    deadline: '2026-03-20', totalTime: 5760, createdAt: '2026-03-01',
    steps: steps('t_i1', [
      'Добавить lint + test шаг',
      'Build Docker образа',
      'Push в registry',
      'Deploy на staging автоматически',
    ]).map(s => ({ ...s, completed: true })),
  },
  {
    id: 't_i2', title: 'Kubernetes манифесты для production',
    subGoalId: 'sg_i1', directionId: 'dir_infra', status: 'active',
    deadline: '2026-04-22', totalTime: 9000, createdAt: '2026-03-10',
    steps: steps('t_i2', [
      'Написать Deployment + Service для каждого сервиса',
      'ConfigMap и Secrets через Vault',
      'HPA для auto-scaling',
      'Ingress с cert-manager',
      'Тест деплоя на staging',
    ]),
  },
  {
    id: 't_i3', title: 'Prometheus + Grafana stack',
    subGoalId: 'sg_i2', directionId: 'dir_infra', status: 'active',
    deadline: '2026-04-24', totalTime: 6300, createdAt: '2026-03-15',
    steps: steps('t_i3', [
      'Установить kube-prometheus-stack',
      'Добавить scrape configs для сервисов',
      'Настроить retention policy',
      'Построить Grafana дашборды',
    ]),
  },
  {
    id: 't_i4', title: 'PagerDuty алерты по критическим метрикам',
    subGoalId: 'sg_i2', directionId: 'dir_infra', status: 'stuck',
    deadline: '2026-04-12', totalTime: 1800, createdAt: '2026-03-25',
    notes: 'Завис на настройке PagerDuty routing rules — нужен доступ от DevOps.',
    steps: steps('t_i4', [
      'Создать escalation policy',
      'Настроить Alertmanager → PagerDuty',
      'Протестировать fire drill',
    ]),
  },
  {
    id: 't_i5', title: 'Security audit и устранение уязвимостей',
    subGoalId: 'sg_i3', directionId: 'dir_infra', status: 'inbox',
    totalTime: 0, createdAt: '2026-04-04',
    steps: steps('t_i5', [
      'Запустить trivy scan на все образа',
      'Снять отчёт по OWASP Top 10',
      'Закрыть Critical и High',
      'Настроить автоматический rescan в CI',
    ]),
  },
]
