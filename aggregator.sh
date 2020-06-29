#!/bin/bash
# 1000 puslses = 1kwh
if [ -z "$1" ]; then
        echo Usage $0 measurements_file_path
        exit 1
else
        FILE=$1
fi
MSUM=0
for day in {1..31}; do
        if [ $day -lt 10 ]; then
                day=0$day
        fi
        LINES=`grep -a ^[0-9][0-9]\/$day $FILE`
        echo Date: $day
        if [ -n "$LINES" ]; then
                DSUM=0
                for hr in {0..23}; do
                        if [ $hr -lt 10 ]; then
                                hr=0$hr
                        fi
                        LIST=$(echo "$LINES" | awk '{print $2, $3}' | grep ^$hr  | awk '{print $2}')
                        SUM=0
                        for m in $LIST; do
                                ((SUM += m))
                        done
                        echo $hr $SUM
                        ((DSUM += SUM)) # day summary update
                done
                echo "Total ($day): $DSUM"
        fi
        ((MSUM += DSUM)) # add daily to monthone
done
echo "Total (month): $MSUM"
