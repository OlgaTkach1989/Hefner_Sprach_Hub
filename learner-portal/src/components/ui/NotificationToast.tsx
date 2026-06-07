import "./NotificationToast.css";

type ToastType = "success" | "error";

type Props = {
  type: ToastType;
  message: string;
  onClose: () => void;
};

export const NotificationToast = ({ type, message, onClose }: Props) => {
  return (
    <div className={`notification-toast notification-toast--${type}`} role="status" aria-live="polite">
      <p>{message}</p>
      <button type="button" onClick={onClose} aria-label="Close notification">
        ×
      </button>
    </div>
  );
};
