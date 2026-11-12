import s from "./account.module.css";

export default function StopsTitle({ title }: { title: { names: string; more: string | null } }) {
  return (
    <>
      {title.names}
      {title.more && <span className={s.moreCount}> {title.more}</span>}
    </>
  );
}
