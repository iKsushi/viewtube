export type User = {
  id: string;
  email: string;
  display_name: string;
  role: "user" | "moderator" | "admin";
  channel_id: string;
  handle: string;
};
export type Channel = {
  id: string;
  name: string;
  handle: string;
  color: string;
  description: string;
  subscribers: number;
  subscribed: boolean;
  is_owner: boolean;
};
export type Video = {
  id: string;
  title: string;
  description: string;
  category: string;
  visibility: "public" | "private";
  status: string;
  hidden: boolean;
  duration: number;
  views: number;
  created_at: string;
  likes: number;
  comment_count: number;
  reaction: number;
  position: number;
  error: string | null;
  is_owner: boolean;
  thumbnail: string | null;
  channel: Pick<Channel, "id" | "name" | "handle" | "color">;
};
export type Page<T> = {
  items: T[];
  total: number;
  page: number;
  limit: number;
};
export type Playlist = {
  id: string;
  title: string;
  visibility: "public" | "private";
  channel_id: string;
  is_owner: boolean;
  videos: Video[];
};
export const categories = [
  "Все",
  "Технологии",
  "Образование",
  "Музыка",
  "Путешествия",
  "Игры",
  "Кино",
  "Наука",
];
export const number = (n: number) =>
  new Intl.NumberFormat("ru-RU", {
    notation: n >= 10000 ? "compact" : "standard",
    maximumFractionDigits: 1,
  }).format(n);
export const duration = (n: number) =>
  `${Math.floor(n / 60)}:${String(Math.floor(n % 60)).padStart(2, "0")}`;
export const plural = (n: number, one: string, few: string, many: string) => {
  const choice = new Intl.PluralRules("ru").select(n);
  return choice === "one" ? one : choice === "few" ? few : many;
};
export function ago(value: string) {
  const days = Math.max(
    0,
    Math.floor((Date.now() - new Date(value).getTime()) / 86400000),
  );
  return days === 0 ? "сегодня" : days === 1 ? "вчера" : `${days} дн. назад`;
}
export const statusLabel: Record<string, string> = {
  draft: "Ожидает файл",
  uploading: "Загрузка",
  queued: "В очереди",
  processing: "Обработка",
  ready: "Опубликовано",
  failed: "Ошибка обработки",
};
