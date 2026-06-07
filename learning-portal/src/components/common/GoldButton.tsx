import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Link } from "react-router-dom";
import styles from "./GoldButton.module.css";

type Size = "lg" | "md";

type BaseProps = {
  children: ReactNode;
  className?: string;
  fullWidth?: boolean;
  size?: Size;
};

type LinkProps = BaseProps & {
  to: string;
  onClick?: never;
  type?: never;
  disabled?: never;
};

type ButtonProps = BaseProps &
  Pick<ButtonHTMLAttributes<HTMLButtonElement>, "onClick" | "type" | "disabled"> & {
    to?: never;
  };

type Props = LinkProps | ButtonProps;

const cn = (...classes: Array<string | undefined | false>) => classes.filter(Boolean).join(" ");

export const GoldButton = (props: Props) => {
  const sizeClass = props.size === "md" ? styles.md : undefined;
  const classes = cn(styles.base, sizeClass, props.fullWidth ? styles.fullWidth : undefined, props.className);

  if (typeof (props as LinkProps).to === "string") {
    const { to, children } = props as LinkProps;
    return (
      <Link to={to} className={classes}>
        {children}
      </Link>
    );
  }

  return (
    <button
      type={props.type ?? "button"}
      onClick={props.onClick}
      disabled={props.disabled}
      className={cn(classes, props.disabled ? styles.disabled : undefined)}
    >
      {props.children}
    </button>
  );
};
