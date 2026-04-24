import React from "react";

const TIME_PATTERN = /^(\d{1,2}):(\d{2})/;

export function formatTime12h(value) {
  if (!value || typeof value !== "string" || !value.includes(":")) {
    return value || "";
  }
  const [rawHour, rawMinute] = value.split(":");
  const hour = Number(rawHour);
  const minute = Number(rawMinute);
  if (!Number.isFinite(hour) || !Number.isFinite(minute)) {
    return value;
  }
  const suffix = hour >= 12 ? "PM" : "AM";
  const displayHour = hour % 12 || 12;
  return `${displayHour}:${String(minute).padStart(2, "0")} ${suffix}`;
}

export function formatTimeRange12h(start, end) {
  return `${formatTime12h(start)} - ${formatTime12h(end)}`;
}

export const TIME_SELECT_OPTIONS = Array.from({ length: 24 * 4 }, (_, index) => {
  const hour = Math.floor(index / 4);
  const minute = (index % 4) * 15;
  const value = `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
  return { value, label: formatTime12h(value) };
});

function getTimeParts(value) {
  const normalizedValue = typeof value === "string" && value.length >= 5 ? value.slice(0, 5) : value || "";
  const match = normalizedValue.match(TIME_PATTERN);
  if (!match) {
    return { normalizedValue, hour: "", minute: "", meridiem: "PM" };
  }

  const rawHour = Number(match[1]);
  const rawMinute = Number(match[2]);
  if (!Number.isFinite(rawHour) || !Number.isFinite(rawMinute)) {
    return { normalizedValue, hour: "", minute: "", meridiem: "PM" };
  }

  return {
    normalizedValue,
    hour: String(rawHour % 12 || 12),
    minute: String(rawMinute).padStart(2, "0"),
    meridiem: rawHour >= 12 ? "PM" : "AM",
  };
}

function buildTimeValue(hourInput, minuteInput, meridiem) {
  const hour = Number(hourInput);
  const minute = Number(minuteInput);
  if (!Number.isInteger(hour) || hour < 1 || hour > 12 || !Number.isInteger(minute) || minute < 0 || minute > 59) {
    return null;
  }

  const hour24 = meridiem === "PM" ? (hour % 12) + 12 : hour % 12;
  return `${String(hour24).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

function cleanNumberInput(value, maxLength) {
  return value.replace(/\D/g, "").slice(0, maxLength);
}

export function TimeSelect({ value, onChange, className = "", disabled = false, ...props }) {
  const currentParts = getTimeParts(value);
  const [hourInput, setHourInput] = React.useState(currentParts.hour);
  const [minuteInput, setMinuteInput] = React.useState(currentParts.minute);
  const [meridiem, setMeridiem] = React.useState(currentParts.meridiem);
  const [isMeridiemOpen, setIsMeridiemOpen] = React.useState(false);

  React.useEffect(() => {
    setHourInput(currentParts.hour);
    setMinuteInput(currentParts.minute);
    setMeridiem(currentParts.meridiem);
  }, [currentParts.normalizedValue]);

  const commitTime = (nextHour, nextMinute, nextMeridiem) => {
    const nextValue = buildTimeValue(nextHour, nextMinute, nextMeridiem);
    if (nextValue) {
      onChange(nextValue);
    }
  };

  const handleHourChange = (event) => {
    const nextHour = cleanNumberInput(event.target.value, 2);
    setHourInput(nextHour);
    commitTime(nextHour, minuteInput, meridiem);
  };

  const handleMinuteChange = (event) => {
    const nextMinute = cleanNumberInput(event.target.value, 2);
    setMinuteInput(nextMinute);
    commitTime(hourInput, nextMinute, meridiem);
  };

  const handleMeridiemChange = (nextMeridiem) => {
    setMeridiem(nextMeridiem);
    setIsMeridiemOpen(false);
    commitTime(hourInput, minuteInput, nextMeridiem);
  };

  const resetInvalidDraft = () => {
    const nextParts = getTimeParts(value);
    setHourInput(nextParts.hour);
    setMinuteInput(nextParts.minute);
    setMeridiem(nextParts.meridiem);
  };

  const normalizeMinuteDraft = () => {
    const minute = Number(minuteInput);
    if (Number.isInteger(minute) && minute >= 0 && minute <= 59) {
      setMinuteInput(String(minute).padStart(2, "0"));
      return;
    }
    resetInvalidDraft();
  };

  return React.createElement(
    "div",
    {
      ...props,
      className: ["time-input", className].filter(Boolean).join(" "),
      role: "group",
      "aria-label": props["aria-label"] || "Time",
    },
    React.createElement("input", {
      className: "time-input__field",
      type: "text",
      inputMode: "numeric",
      pattern: "[0-9]*",
      value: hourInput,
      onChange: handleHourChange,
      onBlur: resetInvalidDraft,
      disabled,
      "aria-label": "Hour",
      placeholder: "hr",
      maxLength: 2,
    }),
    React.createElement("span", { className: "time-input__separator", "aria-hidden": "true" }, ":"),
    React.createElement("input", {
      className: "time-input__field",
      type: "text",
      inputMode: "numeric",
      pattern: "[0-9]*",
      value: minuteInput,
      onChange: handleMinuteChange,
      onBlur: normalizeMinuteDraft,
      disabled,
      "aria-label": "Minutes",
      placeholder: "min",
      maxLength: 2,
    }),
    React.createElement(
      "div",
      {
        className: "time-input__meridiem",
        "aria-label": "Meridiem",
        onBlur: (event) => {
          if (!event.currentTarget.contains(event.relatedTarget)) {
            setIsMeridiemOpen(false);
          }
        },
      },
      React.createElement(
        "button",
        {
          type: "button",
          className: "time-input__period-trigger",
          onClick: () => setIsMeridiemOpen((isOpen) => !isOpen),
          disabled,
          "aria-haspopup": "listbox",
          "aria-expanded": isMeridiemOpen,
        },
        meridiem,
      ),
      isMeridiemOpen
        ? React.createElement(
            "div",
            {
              className: "time-input__period-menu",
              role: "listbox",
              "aria-label": "Meridiem",
            },
            ["AM", "PM"].map((option) =>
              React.createElement(
                "button",
                {
                  key: option,
                  type: "button",
                  role: "option",
                  className:
                    option === meridiem ? "time-input__period-option is-active" : "time-input__period-option",
                  onPointerDown: (event) => {
                    event.preventDefault();
                    handleMeridiemChange(option);
                  },
                  onClick: (event) => {
                    if (event.detail === 0) {
                      handleMeridiemChange(option);
                    }
                  },
                  disabled,
                  "aria-selected": option === meridiem,
                },
                option,
              ),
            ),
          )
        : null,
    ),
  );
}
