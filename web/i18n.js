const APP_TRANSLATIONS = {
  en: {
    actions: "Actions",
    active: "Active",
    addTask: "Add task",
    ai: "AI",
    apiError: "Request failed",
    appTitle: "Personal Assistant Agent",
    calendar: "Calendar",
    calendarConflicts: "Calendar conflicts",
    cancelled: "Cancelled",
    company: "Nofit LTD",
    completed: "Completed",
    conflicts: "Conflicts",
    dailyReport: "Daily Report",
    delete: "Delete",
    demo: "Demo",
    draftReply: "Draft reply",
    dueDate: "Due date",
    emptyCalendar: "No calendar events to show",
    emptyInbox: "No inbox messages to show",
    emptyTasks: "No open tasks",
    error: "Error",
    fyi: "FYI",
    generateReport: "Generate report",
    important: "Important",
    inactive: "Inactive",
    inbox: "Inbox",
    integrationStatus: "Integration status",
    loadDemoData: "Load demo data",
    loading: "Loading",
    messages: "Messages",
    morningBriefing: "Morning Briefing",
    newTask: "New task",
    noSubject: "No subject",
    note: "Note",
    openTasks: "Open tasks",
    priority: "Priority",
    recommendation: "Recommendation",
    refreshCalendar: "Refresh calendar",
    refreshInbox: "Refresh inbox",
    reopenTask: "Reopen task",
    report: "Report",
    routine: "Routine",
    send: "Send",
    sendApproval: "Send the latest briefing to configured messaging channels?",
    sendReport: "Send report",
    sendingNeedsApproval: "Sending requires approval",
    status: "Status",
    systemUpdated: "System updated",
    taskAdded: "Task added",
    taskComplete: "Mark complete",
    tasks: "Tasks",
    urgent: "Urgent",
  },
  he: {
    actions: "פעולות",
    active: "פעיל",
    addTask: "הוספת משימה",
    ai: "בינה מלאכותית",
    apiError: "הבקשה נכשלה",
    appTitle: "Personal Assistant Agent",
    calendar: "יומן",
    calendarConflicts: "התנגשויות ביומן",
    cancelled: "בוטל",
    company: "Nofit LTD",
    completed: "הושלם",
    conflicts: "התנגשויות",
    dailyReport: "דוח יומי",
    delete: "מחיקה",
    demo: "דמו",
    draftReply: "טיוטת תגובה",
    dueDate: "תאריך יעד",
    emptyCalendar: "אין אירועי יומן להצגה",
    emptyInbox: "אין הודעות בתיבת הדואר הנכנס",
    emptyTasks: "אין משימות פתוחות",
    error: "שגיאה",
    fyi: "לידיעה",
    generateReport: "הפקת דוח",
    important: "חשוב",
    inactive: "לא פעיל",
    inbox: "תיבת דואר נכנס",
    integrationStatus: "סטטוס אינטגרציות",
    loadDemoData: "טעינת נתוני דמו",
    loading: "טוען",
    messages: "הודעות",
    morningBriefing: "תדריך בוקר",
    newTask: "משימה חדשה",
    noSubject: "ללא נושא",
    note: "הערה",
    openTasks: "משימות פתוחות",
    priority: "עדיפות",
    recommendation: "המלצה",
    refreshCalendar: "רענון יומן",
    refreshInbox: "רענון תיבת דואר",
    reopenTask: "פתח מחדש",
    report: "דוח",
    routine: "שגרתי",
    send: "שליחה",
    sendApproval: "לשלוח את הדוח האחרון לערוצי ההודעות שהוגדרו?",
    sendReport: "שליחת דוח",
    sendingNeedsApproval: "שליחה דורשת אישור",
    status: "סטטוס",
    systemUpdated: "המערכת מעודכנת",
    taskAdded: "משימה נוספה",
    taskComplete: "סמן כבוצע",
    tasks: "משימות",
    urgent: "דחוף",
  },
};

function appLanguage() {
  return localStorage.getItem("assistant.language") || "en";
}

function appText(key, language = appLanguage()) {
  return APP_TRANSLATIONS[language]?.[key] || APP_TRANSLATIONS.en[key] || key;
}

function applyTranslations(language = appLanguage()) {
  const isHebrew = language === "he";
  document.documentElement.lang = language;
  document.documentElement.dir = isHebrew ? "rtl" : "ltr";

  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = appText(node.dataset.i18n, language);
  });
  document.querySelectorAll("[data-i18n-title]").forEach((node) => {
    node.setAttribute("title", appText(node.dataset.i18nTitle, language));
  });
  document.querySelectorAll("[data-i18n-aria]").forEach((node) => {
    node.setAttribute("aria-label", appText(node.dataset.i18nAria, language));
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    node.setAttribute("placeholder", appText(node.dataset.i18nPlaceholder, language));
  });
}

window.AssistantI18n = {
  applyTranslations,
  appLanguage,
  appText,
  translations: APP_TRANSLATIONS,
};
