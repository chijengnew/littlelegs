import { Fragment } from "react";
import s from "./account.module.css";

export default function Segments({ items }: { items: string[] }) {
  return (
    <>
      {items.map((x, i) => (
        <Fragment key={x}>
          {i > 0 && (
            <span className={s.sep} aria-hidden="true">
              /
            </span>
          )}
          <span>{x}</span>
        </Fragment>
      ))}
    </>
  );
}
