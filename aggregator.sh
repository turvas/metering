#!/bin/bash
# 1000 puslses = 1kwh
FILE=$1
for day in {1..31}; do
        if [ $day -lt 10 ]; then
                day=0$day
        fi
        LINES=`grep -a ^[0-9][0-9]\/$day $FILE`
        echo Date: $day
        if [ -n "$LINES" ]; then
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
                done
        fi
done
