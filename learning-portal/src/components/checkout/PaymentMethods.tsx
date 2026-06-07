import { useTranslation } from "react-i18next";
import styles from "./PaymentMethods.module.css";
import { publicAsset } from "../../utils/publicAsset";

type Props = {
  onChoose: (provider: "klarna" | "sofort" | "paypal") => void;
};

export const PaymentMethods = ({ onChoose }: Props) => {
  const { t } = useTranslation();

  return (
    <div className={styles.wrap}>
      <button type="button" className={styles.btn} onClick={() => onChoose("klarna")}>
        <span className={styles.icon}>K</span>
        <span>{t("checkoutWithKlarna")}</span>
      </button>

      <button type="button" className={styles.btn} onClick={() => onChoose("sofort")}>
        <span className={styles.icon}>S</span>
        <span>{t("checkoutWithSofort")}</span>
      </button>

      <button type="button" className={styles.btn} onClick={() => onChoose("paypal")}>
        <span className={styles.icon}>
          <img src={publicAsset("images/paypal.png")} alt="PayPal" />
        </span>
        <span>{t("checkoutWithPaypal")}</span>
      </button>
    </div>
  );
};
