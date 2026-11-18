# Первая серия сравнения моделей

Трёхстадийное обновление памяти не показало устойчивого преимущества перед одношаговым на этой выборке. Ниже приведены все группы серии. [Общий отчёт с графиками и каталогом ответов](../../docs/research/report.html).

| Набор | Модель | Метод | Верно | Точность | 95% Wilson | USD | Вызовы |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BABILong | GPT-4.1 mini | Reflexive | 14/20 | 70.0% | 48.1–85.5% | $0.1835 | 280 |
| BABILong | GPT-4.1 mini | Summary | 12/20 | 60.0% | 38.7–78.1% | $0.0813 | 122 |
| BABILong | GPT-5.4 mini · low | Reflexive | 12/20 | 60.0% | 38.7–78.1% | $0.4618 | 291 |
| BABILong | GPT-5.4 mini · low | Summary | 15/20 | 75.0% | 53.1–88.8% | $0.1890 | 120 |
| BABILong | GPT-5.4 nano · low | Reflexive | 10/20 | 50.0% | 29.9–70.1% | $0.1165 | 291 |
| BABILong | GPT-5.4 nano · low | Summary | 9/20 | 45.0% | 25.8–65.8% | $0.0484 | 123 |
| BABILong | GPT-5.4 nano · none | Reflexive | 3/20 | 15.0% | 5.2–36.0% | $0.1062 | 292 |
| BABILong | GPT-5.4 nano · none | Summary | 2/20 | 10.0% | 2.8–30.1% | $0.0474 | 129 |
| Смена цели | GPT-4.1 mini | Reflexive | 2/12 | 16.7% | 4.7–44.8% | $0.1321 | 228 |
| Смена цели | GPT-4.1 mini | Summary | 4/12 | 33.3% | 13.8–60.9% | $0.0403 | 111 |
| Смена цели | GPT-5.4 mini · low | Reflexive | 8/12 | 66.7% | 39.1–86.2% | $0.3041 | 244 |
| Смена цели | GPT-5.4 mini · low | Summary | 7/12 | 58.3% | 32.0–80.7% | $0.1388 | 114 |
| Смена цели | GPT-5.4 nano · low | Reflexive | 3/12 | 25.0% | 8.9–53.2% | $0.0845 | 228 |
| Смена цели | GPT-5.4 nano · low | Summary | 8/12 | 66.7% | 39.1–86.2% | $0.0370 | 120 |
| Смена цели | GPT-5.4 nano · none | Reflexive | 2/12 | 16.7% | 4.7–44.8% | $0.0777 | 232 |
| Смена цели | GPT-5.4 nano · none | Summary | 4/12 | 33.3% | 13.8–60.9% | $0.0307 | 111 |
| PersonaMem | GPT-4.1 mini | Полный контекст | 10/16 | 62.5% | 38.6–81.5% | $0.1692 | 16 |
| PersonaMem | GPT-4.1 mini | Последнее окно | 4/16 | 25.0% | 10.2–49.5% | $0.0294 | 16 |
| PersonaMem | GPT-4.1 mini | Reflexive | 7/16 | 43.8% | 23.1–66.8% | $0.8103 | 671 |
| PersonaMem | GPT-4.1 mini | Summary | 8/16 | 50.0% | 28.0–72.0% | $0.3570 | 250 |
| PersonaMem | GPT-5.4 mini · low | Полный контекст | 10/16 | 62.5% | 38.6–81.5% | $0.3227 | 16 |
| PersonaMem | GPT-5.4 mini · low | Последнее окно | 6/16 | 37.5% | 18.5–61.4% | $0.0619 | 16 |
| PersonaMem | GPT-5.4 mini · low | Reflexive | 5/16 | 31.2% | 14.2–55.6% | $2.0572 | 685 |
| PersonaMem | GPT-5.4 mini · low | Summary | 6/16 | 37.5% | 18.5–61.4% | $0.8675 | 254 |
| PersonaMem | GPT-5.4 nano · low | Полный контекст | 9/16 | 56.2% | 33.2–76.9% | $0.0859 | 16 |
| PersonaMem | GPT-5.4 nano · low | Последнее окно | 5/16 | 31.2% | 14.2–55.6% | $0.0159 | 16 |
| PersonaMem | GPT-5.4 nano · low | Reflexive | 5/16 | 31.2% | 14.2–55.6% | $0.6050 | 679 |
| PersonaMem | GPT-5.4 nano · low | Summary | 7/16 | 43.8% | 23.1–66.8% | $0.2707 | 260 |
| PersonaMem | GPT-5.4 nano · none | Полный контекст | 6/16 | 37.5% | 18.5–61.4% | $0.0846 | 16 |
| PersonaMem | GPT-5.4 nano · none | Последнее окно | 4/16 | 25.0% | 10.2–49.5% | $0.0147 | 16 |
| PersonaMem | GPT-5.4 nano · none | Reflexive | 8/16 | 50.0% | 28.0–72.0% | $0.5533 | 674 |
| PersonaMem | GPT-5.4 nano · none | Summary | 5/16 | 31.2% | 14.2–55.6% | $0.2209 | 253 |

## Парное сравнение методов

Положительная разница — в пользу Reflexive. p — точный McNemar без поправки на множественные сравнения.

| Набор | Профиль | Пар | Разница, п.п. | Только Reflexive | Только Summary | p |
| --- | --- | --- | --- | --- | --- | --- |
| BABILong | GPT-4.1 mini | 20 | +10.0 | 5 | 3 | 0.7266 |
| BABILong | GPT-5.4 nano · low | 20 | +5.0 | 3 | 2 | 1.0000 |
| BABILong | GPT-5.4 mini · low | 20 | -15.0 | 3 | 6 | 0.5078 |
| BABILong | GPT-5.4 nano · none | 20 | +5.0 | 1 | 0 | 1.0000 |
| Смена цели | GPT-4.1 mini | 12 | -16.7 | 2 | 4 | 0.6875 |
| Смена цели | GPT-5.4 nano · low | 12 | -41.7 | 1 | 6 | 0.1250 |
| Смена цели | GPT-5.4 mini · low | 12 | +8.3 | 3 | 2 | 1.0000 |
| Смена цели | GPT-5.4 nano · none | 12 | -16.7 | 1 | 3 | 0.6250 |
| PersonaMem | GPT-4.1 mini | 16 | -6.2 | 2 | 3 | 1.0000 |
| PersonaMem | GPT-5.4 nano · low | 16 | -12.5 | 2 | 4 | 0.6875 |
| PersonaMem | GPT-5.4 mini · low | 16 | -6.2 | 1 | 2 | 1.0000 |
| PersonaMem | GPT-5.4 nano · none | 16 | +18.8 | 3 | 0 | 0.2500 |

## До и после повторного чтения

| Набор | Профиль | Метод | Верно до → после | Поиски |
| --- | --- | --- | --- | --- |
| BABILong | GPT-4.1 mini | Reflexive | 14 → 14 из 20 | 0 |
| BABILong | GPT-4.1 mini | Summary | 12 → 12 из 20 | 1 |
| BABILong | GPT-5.4 mini · low | Reflexive | 11 → 12 из 20 | 2 |
| BABILong | GPT-5.4 mini · low | Summary | 15 → 15 из 20 | 0 |
| BABILong | GPT-5.4 nano · low | Reflexive | 10 → 10 из 20 | 2 |
| BABILong | GPT-5.4 nano · low | Summary | 9 → 9 из 20 | 1 |
| BABILong | GPT-5.4 nano · none | Reflexive | 3 → 3 из 20 | 3 |
| BABILong | GPT-5.4 nano · none | Summary | 2 → 2 из 20 | 3 |
| Смена цели | GPT-4.1 mini | Reflexive | 2 → 2 из 12 | 0 |
| Смена цели | GPT-4.1 mini | Summary | 3 → 4 из 12 | 1 |
| Смена цели | GPT-5.4 mini · low | Reflexive | 4 → 8 из 12 | 4 |
| Смена цели | GPT-5.4 mini · low | Summary | 7 → 7 из 12 | 2 |
| Смена цели | GPT-5.4 nano · low | Reflexive | 3 → 3 из 12 | 0 |
| Смена цели | GPT-5.4 nano · low | Summary | 5 → 8 из 12 | 4 |
| Смена цели | GPT-5.4 nano · none | Reflexive | 2 → 2 из 12 | 1 |
| Смена цели | GPT-5.4 nano · none | Summary | 4 → 4 из 12 | 1 |
| PersonaMem | GPT-4.1 mini | Reflexive | 7 → 7 из 16 | 0 |
| PersonaMem | GPT-4.1 mini | Summary | 8 → 8 из 16 | 0 |
| PersonaMem | GPT-5.4 mini · low | Reflexive | 5 → 5 из 16 | 2 |
| PersonaMem | GPT-5.4 mini · low | Summary | 5 → 6 из 16 | 3 |
| PersonaMem | GPT-5.4 nano · low | Reflexive | 5 → 5 из 16 | 1 |
| PersonaMem | GPT-5.4 nano · low | Summary | 6 → 7 из 16 | 3 |
| PersonaMem | GPT-5.4 nano · none | Reflexive | 8 → 8 из 16 | 0 |
| PersonaMem | GPT-5.4 nano · none | Summary | 5 → 5 из 16 | 0 |

## Reasoning low и none у nano

| Набор | Метод | Разница low − none, п.п. | p |
| --- | --- | --- | --- |
| BABILong | Reflexive | +35.0 | 0.0391 |
| BABILong | Summary | +35.0 | 0.0156 |
| Смена цели | Reflexive | +8.3 | 1.0000 |
| Смена цели | Summary | +33.3 | 0.1250 |
| PersonaMem | Полный контекст | +18.8 | 0.2500 |
| PersonaMem | Последнее окно | +6.2 | 1.0000 |
| PersonaMem | Reflexive | -18.8 | 0.2500 |
| PersonaMem | Summary | +12.5 | 0.6250 |

## Как читать результаты

Один прогон на комбинацию. Ошибки остаются в знаменателе. Точности разных наборов не объединяются: они проверяют разные задачи. Полный контекст использует большее окно. Небольшие выборки и несколько сравнений ограничивают выводы. До/после поиска — наблюдение в одном прогоне, не отдельный контроль без поиска.

Индивидуальные ответы: [CSV](predictions.csv) и [JSON](results.json). Условия: [protocol.json](protocol.json). Расходы с отладкой: [receipts.csv](receipts.csv). Большинство полных платных журналов в этом клоне отсутствуют.
