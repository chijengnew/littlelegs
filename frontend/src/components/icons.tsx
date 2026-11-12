import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

export function UserIcon({ size = 22, ...rest }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="none" aria-hidden="true" focusable="false" {...rest}>
      <circle cx="12" cy="8.5" r="3.75" fill="currentColor" fillOpacity="0.16" stroke="currentColor" strokeWidth="1.8" />
      <path
        d="M4.75 19.25c1.2-3.3 4-5 7.25-5s6.05 1.7 7.25 5"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}

const BRAND_PATH =
  "M208.45881,721.56894 C220.63518,720.06315 232.39778,715.84736 242.97925,709.57985 C252.61204,703.87426 261.26599,696.46837 269.04069,688.40005 C284.46376,672.39452 296.42671,653.78217 308.52864,635.15795 C332.64632,598.04213 357.31595,560.87915 390.50336,531.37497 C407.74484,516.04699 427.28526,502.78613 449.44602,496.67481 C463.00234,492.93635 477.53921,491.87331 491.30778,494.48838 C502.77603,496.66655 513.71126,501.39647 523.49151,507.84237 C532.80297,513.97929 541.06753,521.67162 548.54288,529.97579 C555.83723,538.07889 562.38012,546.76455 568.73690,555.58317 C581.69898,573.56519 593.88725,592.10008 607.55103,609.58574 C621.09288,626.91537 636.08402,643.21441 653.49215,656.72173 C672.00819,671.08869 693.25865,682.29728 715.92312,687.53057 C742.63282,693.69792 771.30632,691.56666 797.55170,683.06070 C819.46239,675.95958 839.68079,664.41556 857.42958,649.75116 C874.55549,635.60138 889.38209,618.54638 899.29128,598.62745 C910.99367,575.10391 915.83787,547.58612 907.73175,522.69308 C904.20676,511.86820 898.23287,501.53966 890.17819,493.41501 C882.04974,485.21595 871.80222,479.26132 860.69315,476.45921 C847.20410,473.05678 832.44480,474.30234 819.46939,479.40065 C809.11032,483.47093 799.88827,489.99689 791.60605,497.43718 C783.53040,504.69191 776.34829,512.81594 768.44287,520.46854 C760.13424,528.51146 751.02664,536.03365 740.57840,540.58473 C734.49895,543.23283 727.96560,544.87502 721.41044,545.11168 C714.66006,545.35538 707.88655,544.10859 701.63650,541.54550 C691.60162,537.43027 682.91614,529.92181 675.51844,521.62913 C660.24234,504.50492 650.45749,484.03671 641.20239,463.41347 C631.66718,442.16605 622.69426,420.75407 611.49376,400.28375 C600.77675,380.69709 588.02033,361.97254 571.85825,346.51654 C555.53691,330.90823 535.74246,318.63321 514.45976,311.08303 C488.62568,301.91822 460.59874,299.71519 433.27906,302.58875 C407.85475,305.26294 383.04296,312.33375 359.47517,322.12866 C317.88402,339.41418 280.16708,365.18344 246.68619,395.48986 C214.00801,425.06967 185.36519,458.97170 161.13510,495.52746 C148.49934,514.59094 137.06363,534.37610 128.07333,555.48838 C117.69223,579.86675 110.57170,606.01462 112.34742,632.35052 C113.96134,656.28675 122.92418,680.37832 139.66814,697.52293 C147.60633,705.65106 157.29344,712.21777 167.90876,716.44867 C180.69959,721.54666 194.83808,723.25334 208.45881,721.56894 Z";

export function BrandLogo({ height = 22, tone = "terracotta" }: { height?: number; tone?: "terracotta" | "black" | "white" }) {
  return (
    <svg
      viewBox="96 285 832 452"
      height={height}
      width={(height * 832) / 452}
      aria-hidden="true"
      focusable="false"
      style={{ fill: `var(--brand-${tone})`, display: "block" }}
    >
      <path d={BRAND_PATH} />
    </svg>
  );
}

const ACCENT = { fill: "var(--orange-500)", fillOpacity: 0.3 } as const;

export function CalendarIcon({ size = 28, ...rest }: IconProps) {
  return (
    <svg viewBox="0 0 28 28" width={size} height={size} fill="none" aria-hidden="true" focusable="false" {...rest}>
      <rect x="4" y="6" width="20" height="18" rx="4" style={ACCENT} />
      <rect x="4" y="6" width="20" height="18" rx="4" stroke="currentColor" strokeWidth="1.8" />
      <path d="M4 11.5h20M9.5 3.5v5M18.5 3.5v5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="10" cy="17" r="1.6" fill="currentColor" />
      <circle cx="14" cy="17" r="1.6" fill="currentColor" />
    </svg>
  );
}

export function PinIcon({ size = 28, ...rest }: IconProps) {
  return (
    <svg viewBox="0 0 28 28" width={size} height={size} fill="none" aria-hidden="true" focusable="false" {...rest}>
      <path d="M14 3.5c-4.7 0-8.5 3.6-8.5 8.2 0 6 8.5 12.8 8.5 12.8s8.5-6.8 8.5-12.8c0-4.6-3.8-8.2-8.5-8.2Z" style={ACCENT} />
      <path
        d="M14 3.5c-4.7 0-8.5 3.6-8.5 8.2 0 6 8.5 12.8 8.5 12.8s8.5-6.8 8.5-12.8c0-4.6-3.8-8.2-8.5-8.2Z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <path d="m10.5 11.6 2.4 2.4 4.6-4.6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function RouteIcon({ size = 28, ...rest }: IconProps) {
  return (
    <svg viewBox="0 0 28 28" width={size} height={size} fill="none" aria-hidden="true" focusable="false" {...rest}>
      <circle cx="7" cy="7" r="3.5" style={ACCENT} />
      <circle cx="21" cy="21" r="3.5" style={ACCENT} />
      <circle cx="7" cy="7" r="3.5" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="21" cy="21" r="3.5" stroke="currentColor" strokeWidth="1.8" />
      <path d="M10.5 7H17a4 4 0 0 1 0 8h-6a4 4 0 0 0 0 8h6.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function Small({ size = 18, children, ...rest }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {children}
    </svg>
  );
}

export function ListIcon(props: IconProps) {
  return (
    <Small {...props}>
      <path d="M9 6h11M9 12h11M9 18h11" />
      <circle cx="4.5" cy="6" r="1" fill="currentColor" />
      <circle cx="4.5" cy="12" r="1" fill="currentColor" />
      <circle cx="4.5" cy="18" r="1" fill="currentColor" />
    </Small>
  );
}

export function MapIcon(props: IconProps) {
  return (
    <Small {...props}>
      <path d="m3.5 6.5 5.5-2.5 6 2.5 5.5-2.5v13.5l-5.5 2.5-6-2.5-5.5 2.5Z" />
      <path d="M9 4v13.5M15 6.5V20" />
    </Small>
  );
}

export function TimelineIcon(props: IconProps) {
  return (
    <Small {...props}>
      <path d="M6 4v16" />
      <circle cx="6" cy="7" r="2" fill="currentColor" />
      <circle cx="6" cy="17" r="2" fill="currentColor" />
      <path d="M11 7h9M11 17h6" />
    </Small>
  );
}

export function CarIcon(props: IconProps) {
  return (
    <Small {...props}>
      <path d="M5 16.5V12l2-5h10l2 5v4.5Z" />
      <path d="M5 12h14" />
      <circle cx="8" cy="16.5" r="1.8" fill="currentColor" />
      <circle cx="16" cy="16.5" r="1.8" fill="currentColor" />
    </Small>
  );
}

export function MealIcon(props: IconProps) {
  return (
    <Small {...props}>
      <path d="M7 3.5v17M4.5 3.5V8a2.5 2.5 0 0 0 5 0V3.5" />
      <path d="M16.5 20.5V3.5c2 1 3 3.5 3 7h-3" />
    </Small>
  );
}

export function MoonIcon(props: IconProps) {
  return (
    <Small {...props}>
      <path d="M19.5 14.5A7.5 7.5 0 0 1 9.5 4.5a7.5 7.5 0 1 0 10 10Z" />
    </Small>
  );
}

export function ClockIcon(props: IconProps) {
  return (
    <Small {...props}>
      <circle cx="12" cy="12" r="8" />
      <path d="M12 7.5V12l3 2" />
    </Small>
  );
}

export function FlagIcon(props: IconProps) {
  return (
    <Small {...props}>
      <path d="M5.5 20.5v-16M5.5 4.5h11l-2 4 2 4h-11" />
    </Small>
  );
}

export function MailIcon(props: IconProps) {
  return (
    <Small {...props}>
      <rect x="3.5" y="5.5" width="17" height="13" rx="2.5" />
      <path d="m4.5 7 7.5 6 7.5-6" />
    </Small>
  );
}

export function MapPinIcon(props: IconProps) {
  return (
    <Small {...props}>
      <path d="M12 21.5s-6.8-5.6-6.8-11.2a6.8 6.8 0 0 1 13.6 0c0 5.6-6.8 11.2-6.8 11.2Z" fill="var(--orange-500)" />
      <circle cx="12" cy="10.3" r="2.5" fill="var(--surface)" />
    </Small>
  );
}

export function LocateIcon(props: IconProps) {
  return (
    <Small {...props}>
      <circle cx="12" cy="12" r="6.5" />
      <circle cx="12" cy="12" r="2.2" fill="currentColor" />
      <path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3" />
    </Small>
  );
}

export function PencilIcon(props: IconProps) {
  return (
    <Small {...props}>
      <path d="M15.5 4.5 19.5 8.5 9 19H5v-4Z" />
      <path d="m13.5 6.5 4 4" />
    </Small>
  );
}

export function UmbrellaIcon(props: IconProps) {
  return (
    <Small {...props}>
      <path d="M3.5 12a8.5 8.5 0 0 1 17 0Z" />
      <path d="M12 12v6.5a2 2 0 0 1-4 0M12 3.5v-1" />
    </Small>
  );
}

export function CheckIcon(props: IconProps) {
  return (
    <Small {...props}>
      <path d="m5 12.5 4.5 4.5L19 7.5" />
    </Small>
  );
}

export function CloseIcon(props: IconProps) {
  return (
    <Small {...props}>
      <path d="M6.5 6.5 17.5 17.5M17.5 6.5 6.5 17.5" />
    </Small>
  );
}

export function PlusIcon(props: IconProps) {
  return (
    <Small {...props}>
      <path d="M12 5v14M5 12h14" />
    </Small>
  );
}

export function ArrowDownIcon(props: IconProps) {
  return (
    <Small {...props}>
      <path d="M12 5v14M6 13l6 6 6-6" />
    </Small>
  );
}

export function ArrowLeftIcon(props: IconProps) {
  return (
    <Small {...props}>
      <path d="M19 12H5M11 6l-6 6 6 6" />
    </Small>
  );
}

export function ArrowRightIcon(props: IconProps) {
  return (
    <Small {...props}>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </Small>
  );
}

export function EyeIcon(props: IconProps) {
  return (
    <Small {...props}>
      <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" />
      <circle cx="12" cy="12" r="3" />
    </Small>
  );
}

export function EyeOffIcon(props: IconProps) {
  return (
    <Small {...props}>
      <path d="M9.9 5.8A9.4 9.4 0 0 1 12 5.5c6 0 9.5 6.5 9.5 6.5a17 17 0 0 1-2.6 3.4M6.4 6.9C3.9 8.6 2.5 12 2.5 12S6 18.5 12 18.5c1.7 0 3.2-.5 4.5-1.2" />
      <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2M3.5 3.5l17 17" />
    </Small>
  );
}

export function LogoutIcon(props: IconProps) {
  return (
    <Small {...props}>
      <path d="M14 4.5H7a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h7" />
      <path d="M11 12h9.5M17 8.5l3.5 3.5-3.5 3.5" />
    </Small>
  );
}

export function NavigateIcon(props: IconProps) {
  return (
    <Small {...props}>
      <path d="M4.5 11.2 19.5 4.5l-6.7 15-1.9-6.4Z" />
    </Small>
  );
}

export function AlertIcon(props: IconProps) {
  return (
    <Small {...props}>
      <path d="M12 4.5 21 19.5H3Z" />
      <path d="M12 10v4M12 16.8v.2" />
    </Small>
  );
}

export function HeartIcon(props: IconProps) {
  return (
    <Small {...props}>
      <path d="M12 19.5s-7.5-4.4-7.5-9.6A4.2 4.2 0 0 1 12 7.6a4.2 4.2 0 0 1 7.5 2.3c0 5.2-7.5 9.6-7.5 9.6Z" />
    </Small>
  );
}

const CHUNKY_ARROW =
  "M12 4.5c.5 0 1 .2 1.4.6l5.6 6.1c.8.9.2 2.3-1 2.3H15v5.2c0 .8-.6 1.3-1.3 1.3h-3.4c-.8 0-1.3-.6-1.3-1.3v-5.2H6c-1.2 0-1.8-1.4-1-2.3l5.6-6.1c.4-.4.9-.6 1.4-.6Z";

export function ChunkyUpIcon({ size = 20, ...rest }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true" focusable="false" {...rest}>
      <path d={CHUNKY_ARROW} fill="currentColor" />
    </svg>
  );
}

export function ChunkyDownIcon({ size = 20, ...rest }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true" focusable="false" {...rest}>
      <path d={CHUNKY_ARROW} fill="currentColor" transform="rotate(180 12 12)" />
    </svg>
  );
}

export function ChunkyCloseIcon({ size = 20, ...rest }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="none" aria-hidden="true" focusable="false" {...rest}>
      <path d="M7.5 7.5 16.5 16.5M16.5 7.5 7.5 16.5" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" />
    </svg>
  );
}
