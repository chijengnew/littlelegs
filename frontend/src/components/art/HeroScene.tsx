import { MascotShape } from "./Mascot";
import a from "./art.module.css";

const FLOWERS: [number, number, "flower" | "flowerSun"][] = [[40, 452, "flower"], [78, 470, "flowerSun"], [114, 452, "flower"], [548, 466, "flowerSun"], [584, 448, "flower"]];
const PRINTS: [number, number, number][] = [[468, 486, -20], [450, 478, -10], [432, 486, -24]];

function Car() {
  return (
    <>
      <rect x="22" y="-7" width="20" height="7" rx="2" className={a.luggage} />
      <path d="M12 12 L20 0 H44 L54 12 Z" className={a.car} />
      <rect x="0" y="10" width="62" height="22" rx="10" className={a.car} />
      <path d="M22 3 H33 V12 H16 Z" className={a.paper} />
      <path d="M36 3 H43 L50 12 H36 Z" className={a.paper} />
      <circle cx="15" cy="33" r="7" className={a.wheel} />
      <circle cx="15" cy="33" r="2.5" className={a.paper} />
      <circle cx="48" cy="33" r="7" className={a.wheel} />
      <circle cx="48" cy="33" r="2.5" className={a.paper} />
    </>
  );
}

function Family() {
  return (
    <>
      <ellipse cx="236" cy="476.2" rx="26.9" ry="4.5" className={a.shade} />
      <path d="M226.8 378.4 L220.6 394.3 A3.4 3.4 0 0 0 226.8 396.9 L234 381.5 A3.9 3.9 0 0 0 226.8 378.4ZM220.4 394.8 L217.6 409.5 A2.8 2.8 0 0 0 223 410.8 L227 396.4 A3.4 3.4 0 0 0 220.4 394.8Z" className={a.skin2} />
      <circle cx="220.3" cy="412.4" r="4.5" className={a.skin2} />
      <path d="M225.1 413 L224.3 440 A5 5 0 0 0 234.3 440.8 L237.9 414.1 A6.4 6.4 0 0 0 225.1 413ZM224.6 438.6 L215.5 464.7 A3.9 3.9 0 0 0 222.9 467.6 L234 442.2 A5 5 0 0 0 224.6 438.6Z" className={a.pantsBlue} />
      <path d="M212.4 468.2 L222.7 475.3 A3.6 3.6 0 0 0 226.9 469.4 L217 461.9 A3.9 3.9 0 0 0 212.4 468.2Z" className={a.shoe} />
      <path d="M-10 -89 C-13 -77 -12 -65 -11 -53 L11 -53 C12 -65 13 -77 10 -89 C4 -92 -4 -92 -10 -89 Z" transform="translate(236 474) scale(1.12)" className={a.shirtSun} />
      <path d="M234.2 415.1 L242.3 441.6 A5 5 0 0 0 252.1 439.2 L246.7 412 A6.4 6.4 0 0 0 234.2 415.1ZM242.2 441 L246.7 467.8 A3.9 3.9 0 0 0 254.4 466.8 L252.2 439.8 A5 5 0 0 0 242.2 441Z" className={a.pantsBlue} />
      <path d="M246.8 474.5 L259.2 475.4 A3.6 3.6 0 0 0 259.8 468.1 L247.6 466.7 A3.9 3.9 0 0 0 246.8 474.5Z" className={a.shoe} />
      <path d="M232.1 366.5 L232.1 375.4 A3.9 3.9 0 0 0 239.9 375.4 L239.9 366.5 A3.9 3.9 0 0 0 232.1 366.5Z" className={a.skin2} />
      <ellipse cx="237.1" cy="356.4" rx="12.9" ry="14.6" className={a.skin2} />
      <path d="M-10 -107 C-11 -117 -3 -121 4 -120 C10 -119 14 -114 13 -108 C9 -112 3 -112 -1 -110 C-4 -108 -7 -104 -9 -100 C-11 -102 -11 -104 -10 -107 Z" transform="translate(236 474) scale(1.12)" className={a.hair2} />
      <ellipse cx="222.6" cy="349.7" rx="5.6" ry="6.7" transform="rotate(-20 222.6 349.7)" className={a.hair2} />
      <path d="M242.7 382.6 L258.2 377.6 A3.4 3.4 0 0 0 256.4 371.1 L240.5 375 A3.9 3.9 0 0 0 242.7 382.6ZM257.6 377.7 L271 376 A2.8 2.8 0 0 0 270.5 370.4 L257 371 A3.4 3.4 0 0 0 257.6 377.7Z" className={a.skin2} />
      <path d="M243.2 382.5 L249.7 379.7 A4.5 4.5 0 0 0 246.9 371.2 L240 372.9 A5 5 0 0 0 243.2 382.5Z" className={a.shirtSun} />
      <ellipse cx="302" cy="474.2" rx="49.3" ry="5.6" className={a.shade} />
      <path d="M286.4 302.9 L280.5 335.5 A4.8 4.8 0 0 0 289.9 337.4 L297.4 305.1 A5.6 5.6 0 0 0 286.4 302.9ZM280.6 335.4 L274.7 364.7 A3.9 3.9 0 0 0 282.3 366.5 L289.8 337.6 A4.8 4.8 0 0 0 280.6 335.4Z" className={a.skin3} />
      <path d="M284.2 301.3 L282 318.4 A6.7 6.7 0 0 0 295.1 321 L299.6 304.4 A7.8 7.8 0 0 0 284.2 301.3Z" className={a.shirtOrange} />
      <circle cx="277.4" cy="371.2" r="6.2" className={a.skin3} />
      <path d="M284.7 368 L283 415.3 A7.8 7.8 0 0 0 298.6 416.7 L305.9 370 A10.6 10.6 0 0 0 284.7 368ZM283.4 413.5 L270.7 457.8 A5.9 5.9 0 0 0 281.8 461.5 L298.2 418.5 A7.8 7.8 0 0 0 283.4 413.5Z" className={a.pants} />
      <path d="M267.2 463 L282.1 473.8 A5 5 0 0 0 288.3 465.8 L274.1 454.1 A5.6 5.6 0 0 0 267.2 463Z" className={a.shoe} />
      <path d="M-29 -148 C-31 -138 -31 -120 -28 -108 C-24 -104 -15 -104 -11 -108 L-11 -150 C-16 -154 -25 -154 -29 -148 Z" transform="translate(302 472) scale(1.12)" className={a.pack} />
      <path d="M-29 -128 L-11 -128 L-11 -121 L-29 -121 Z" transform="translate(302 472) scale(1.12)" className={a.packDark} />
      <path d="M-13 -157 C-18 -141 -17 -118 -15 -98 L16 -98 C17 -118 19 -141 14 -157 C7 -161 -6 -161 -13 -157 Z" transform="translate(302 472) scale(1.12)" className={a.shirtOrange} />
      <path d="M-15 -101 L16 -101 L17 -86 L-16 -86 Z" transform="translate(302 472) scale(1.12)" className={a.pants} />
      <path d="M298.3 371.2 L311.1 417.6 A7.8 7.8 0 0 0 326.5 414.4 L319.1 366.7 A10.6 10.6 0 0 0 298.3 371.2ZM311 416.9 L318.6 462.6 A5.9 5.9 0 0 0 330.2 461.2 L326.6 415.1 A7.8 7.8 0 0 0 311 416.9Z" className={a.pants} />
      <path d="M319.3 472 L339.5 473.6 A5 5 0 0 0 340.6 463.6 L320.5 460.8 A5.6 5.6 0 0 0 319.3 472Z" className={a.shoe} />
      <path d="M287.5 298.7 L294.2 341.3 A2.2 2.2 0 0 0 298.6 340.6 L291.9 298.1 A2.2 2.2 0 0 0 287.5 298.7Z" className={a.packDark} />
      <path d="M297.5 283.8 L297.5 298.4 A5.6 5.6 0 0 0 308.7 298.4 L308.7 283.8 A5.6 5.6 0 0 0 297.5 283.8Z" className={a.skin3} />
      <ellipse cx="305.4" cy="269.3" rx="14.6" ry="17.4" className={a.skin3} />
      <path d="M-11 -183 C-12 -195 -3 -200 6 -199 C14 -198 18 -191 16 -183 C11 -188 4 -189 -1 -186 C-4 -182 -6 -177 -9 -172 C-12 -175 -12 -179 -11 -183 Z" transform="translate(302 472) scale(1.12)" className={a.hair1} />
      <path d="M-12 -186 C-11 -199 2 -205 11 -201 C17 -198 19 -192 18 -187 Z" transform="translate(302 472) scale(1.12)" className={a.hat} />
      <path d="M6 -188 L30 -186 C31 -184 29 -182 26 -182 L6 -183 Z" transform="translate(302 472) scale(1.12)" className={a.hat} />
      <path d="M307.9 306.9 L318.8 336.9 A4.8 4.8 0 0 0 327.8 333.9 L318.5 303.3 A5.6 5.6 0 0 0 307.9 306.9ZM319.7 338.5 L336 355.9 A3.9 3.9 0 0 0 341.9 350.7 L326.9 332.2 A4.8 4.8 0 0 0 319.7 338.5Z" className={a.skin3} />
      <path d="M305.6 304.9 L311.2 321.4 A6.7 6.7 0 0 0 324.2 317.9 L320.8 300.9 A7.8 7.8 0 0 0 305.6 304.9Z" className={a.shirtOrange} />
      <circle cx="342.3" cy="356.6" r="6.2" className={a.skin3} />
      <ellipse cx="394.2" cy="478.2" rx="26.9" ry="4.5" className={a.shade} />
      <path d="M389.8 385.5 L381.3 400.3 A3.4 3.4 0 0 0 387 403.8 L396.5 389.6 A3.9 3.9 0 0 0 389.8 385.5ZM381 400.9 L377 413.4 A2.8 2.8 0 0 0 382.3 415.4 L387.3 403.2 A3.4 3.4 0 0 0 381 400.9Z" className={a.skin1} />
      <circle cx="378.6" cy="416.6" r="4.5" className={a.skin1} />
      <path d="M382 417.2 L371.8 440.1 A5 5 0 0 0 380.8 444.7 L393 422.8 A6.2 6.2 0 0 0 382 417.2ZM377.7 437.6 L361.7 434.2 A3.9 3.9 0 0 0 359.6 441.7 L374.9 447.2 A5 5 0 0 0 377.7 437.6Z" className={a.pants} />
      <path d="M354.7 434.4 L351.6 444.6 A3.6 3.6 0 0 0 358.5 446.9 L362.1 436.9 A3.9 3.9 0 0 0 354.7 434.4Z" className={a.shoe} />
      <path d="M-3 -83 C-9 -72 -11 -61 -10 -48 L9 -47 C12 -58 15 -69 15 -80 C9 -85 2 -86 -3 -83 Z" transform="translate(392 476) scale(1.12)" className={a.shirtPaper} />
      <path d="M-6 -72 C-2 -70 9 -68 14 -70 L14 -64 C9 -62 -2 -63 -8 -66 Z" transform="translate(392 476) scale(1.12)" className={a.shirtOrange} />
      <path d="M389.6 422.2 L400.7 447.6 A5 5 0 0 0 410.1 443.9 L401.1 417.8 A6.2 6.2 0 0 0 389.6 422.2ZM400.5 446.7 L406.1 471.1 A3.9 3.9 0 0 0 413.8 469.7 L410.4 444.9 A5 5 0 0 0 400.5 446.7Z" className={a.pants} />
      <path d="M406.2 477.7 L419.7 478.5 A3.6 3.6 0 0 0 420.3 471.3 L406.9 469.9 A3.9 3.9 0 0 0 406.2 477.7Z" className={a.shoe} />
      <path d="M396 377.9 L397.1 386.9 A3.9 3.9 0 0 0 404.8 385.9 L403.7 377 A3.9 3.9 0 0 0 396 377.9Z" className={a.skin1} />
      <ellipse cx="402.1" cy="367.4" rx="12.3" ry="14" className={a.skin1} />
      <path d="M-1 -101 C-3 -110 4 -115 11 -114 C17 -113 21 -108 20 -101 C17 -105 11 -106 7 -104 C4 -101 2 -98 0 -95 C-2 -97 -2 -99 -1 -101 Z" transform="translate(392 476) scale(1.12)" className={a.hair1} />
      <path d="M408.1 391.5 L420 379.9 A3.4 3.4 0 0 0 415.5 375 L402.8 385.7 A3.9 3.9 0 0 0 408.1 391.5ZM420.6 379.3 L429 365.6 A2.8 2.8 0 0 0 424.4 362.4 L415 375.6 A3.4 3.4 0 0 0 420.6 379.3Z" className={a.skin1} />
      <path d="M409 391.1 L414.2 385.1 A4.5 4.5 0 0 0 407.9 378.8 L401.9 384 A5 5 0 0 0 409 391.1Z" className={a.shirtPaper} />
      <circle cx="427.8" cy="361.8" r="4.5" className={a.skin1} />
    </>
  );
}

export default function HeroScene() {
  return (
    <svg viewBox="0 0 600 500" className={`${a.svg} ${a.day}`} aria-hidden="true" focusable="false" preserveAspectRatio="xMidYMax slice">
      <rect width="600" height="500" className={a.sky} />
      <circle cx="470" cy="140" r="84" className={a.sunRing} />
      <circle cx="470" cy="140" r="56" className={a.sun} />
      <circle cx="110" cy="158" r="22" className={a.cloud} />
      <circle cx="140" cy="146" r="30" className={a.cloud} />
      <circle cx="172" cy="160" r="20" className={a.cloud} />
      <rect x="88" y="158" width="106" height="22" rx="11" className={a.cloud} />
      <circle cx="306" cy="150.6" r="15.4" className={a.cloud} />
      <circle cx="327" cy="142.2" r="21" className={a.cloud} />
      <circle cx="349.4" cy="152" r="14" className={a.cloud} />
      <rect x="290.6" y="150.6" width="74.2" height="15.4" rx="7.7" className={a.cloud} />
      <path d="M0 296 C 80 246 170 236 262 274 C 340 308 420 246 512 242 C 556 240 584 250 600 260 V500 H0 Z" className={a.hillFar} />
      <path d="M150 202 c-12 0-21 9-21 21 c0 16 21 33 21 33 s21-17 21-33 c0-12-9-21-21-21 z" className={a.pin} />
      <circle cx="150" cy="223" r="7.5" className={a.ink} />
      <path d="M534 206 c-9 0-16 7-16 16 c0 12 16 25 16 25 s16-13 16-25 c0-9-7-16-16-16 z" className={a.pinSun} />
      <circle cx="534" cy="222" r="5.5" className={a.ink} />
      <path d="M0 346 C 110 296 214 300 318 336 C 410 368 500 308 600 316 V500 H0 Z" className={a.hill} />
      <rect x="64" y="300" width="8" height="34" rx="3" className={a.trunk} />
      <circle cx="68" cy="288" r="28" className={a.leaf} />
      <rect x="556" y="304" width="7" height="30" rx="3" className={a.trunk} />
      <circle cx="559" cy="292" r="22" className={a.leaf} />
      <circle cx="52" cy="302" r="16" className={a.leafDark} />
      <path d="M0 408 C 120 382 250 378 380 394 C 480 408 548 420 600 412 V500 H0 Z" className={a.ground} />
      <path d="M196 500 C 230 452 330 430 384 402 C 424 380 452 358 508 342" className={a.road} />
      <path d="M196 500 C 230 452 330 430 384 402 C 424 380 452 358 508 342" className={a.roadLine} />
      <g transform="translate(462 312) rotate(-12)">
        <Car />
      </g>
      {FLOWERS.map(([x, y, cls]) => (
        <g key={`${x}-${y}`}>
          <path d={`M${x} ${y + 14} V${y + 4}`} className={a.stem} />
          <circle cx={x} cy={y} r="5" className={a[cls]} />
        </g>
      ))}
      {PRINTS.map(([x, y, r]) => (
        <ellipse key={`${x}-${y}`} cx={x} cy={y} rx="3.5" ry="5" transform={`rotate(${r} ${x} ${y})`} className={a.print} />
      ))}
      <Family />
      <g transform="translate(500 472) scale(0.72)">
        <MascotShape />
      </g>
    </svg>
  );
}

const WIDE_STARS: [number, number, number][] = [[48, 56, 2], [210, 34, 1.5], [372, 72, 2], [530, 30, 1.5], [690, 98, 2], [866, 36, 1.5], [1178, 52, 2], [1160, 236, 1.5]];
const WIDE_FLOWERS: [number, number, "flower" | "flowerSun"][] = [[56, 570, "flower"], [92, 584, "flowerSun"], [128, 572, "flower"], [1132, 566, "flowerSun"], [1170, 552, "flower"]];
const WIDE_PRINTS: [number, number, number][] = [[672, 584, -20], [652, 576, -10], [632, 584, -24]];

export function HeroWideScene({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 1200 600" className={className ?? a.svg} aria-hidden="true" focusable="false" preserveAspectRatio="xMaxYMax slice">
      <rect width="1200" height="600" className={a.sky} />
      {WIDE_STARS.map(([x, y, r]) => <circle key={`${x}-${y}`} cx={x} cy={y} r={r} className={a.star} />)}
      <circle cx="1010" cy="246" r="92" className={a.sunRing} />
      <circle cx="1010" cy="246" r="64" className={a.sun} />
      <g transform="translate(640 50)" className={a.wideCloudNear}>
        <circle cx="110" cy="158" r="22" className={a.cloud} />
        <circle cx="140" cy="146" r="30" className={a.cloud} />
        <circle cx="172" cy="160" r="20" className={a.cloud} />
        <rect x="88" y="158" width="106" height="22" rx="11" className={a.cloud} />
      </g>
      <g transform="translate(800 90)">
        <circle cx="306" cy="150.6" r="15.4" className={a.cloud} />
        <circle cx="327" cy="142.2" r="21" className={a.cloud} />
        <circle cx="349.4" cy="152" r="14" className={a.cloud} />
        <rect x="290.6" y="150.6" width="74.2" height="15.4" rx="7.7" className={a.cloud} />
      </g>
      <path d="M0 470 C 220 462 420 452 580 430 C 740 408 830 330 960 318 C 1060 309 1140 322 1200 334 V600 H0 Z" className={a.hillFar} />
      <g transform="translate(755 30)">
        <path d="M150 202 c-12 0-21 9-21 21 c0 16 21 33 21 33 s21-17 21-33 c0-12-9-21-21-21 z" className={a.pin} />
        <circle cx="150" cy="223" r="7.5" className={a.ink} />
      </g>
      <g transform="translate(616 84)">
        <path d="M534 206 c-9 0-16 7-16 16 c0 12 16 25 16 25 s16-13 16-25 c0-9-7-16-16-16 z" className={a.pinSun} />
        <circle cx="534" cy="222" r="5.5" className={a.ink} />
      </g>
      <path d="M0 512 C 240 504 440 494 620 472 C 780 452 880 404 1010 398 C 1100 394 1160 404 1200 412 V600 H0 Z" className={a.hill} />
      <rect x="1126" y="370" width="8" height="36" rx="3" className={a.trunk} />
      <circle cx="1130" cy="358" r="28" className={a.leaf} />
      <circle cx="1112" cy="372" r="16" className={a.leafDark} />
      <rect x="596" y="470" width="7" height="30" rx="3" className={a.trunk} />
      <circle cx="599" cy="460" r="22" className={a.leaf} />
      <path d="M0 556 C 280 548 560 540 760 524 C 900 512 1040 500 1200 506 V600 H0 Z" className={a.ground} />
      <path d="M540 600 C 640 562 820 546 940 522 C 1040 502 1110 476 1200 458" className={a.road} />
      <path d="M540 600 C 640 562 820 546 940 522 C 1040 502 1110 476 1200 458" className={a.roadLine} />
      <g transform="translate(1036 446) rotate(-12) scale(1.25)">
        <Car />
      </g>
      {WIDE_FLOWERS.map(([x, y, cls]) => (
        <g key={`${x}-${y}`}>
          <path d={`M${x} ${y + 14} V${y + 4}`} className={a.stem} />
          <circle cx={x} cy={y} r="5" className={a[cls]} />
        </g>
      ))}
      {WIDE_PRINTS.map(([x, y, r]) => (
        <ellipse key={`${x}-${y}`} cx={x} cy={y} rx="3.5" ry="5" transform={`rotate(${r} ${x} ${y})`} className={a.print} />
      ))}
      <g transform="translate(456 10) scale(1.15)">
        <Family />
        <g transform="translate(500 472) scale(0.72)">
          <MascotShape />
        </g>
      </g>
    </svg>
  );
}
