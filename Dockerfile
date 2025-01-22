FROM docker.io/ringcentral/jdk:17
ARG JAR_NAME='passwordlessdbapp-0.0.1-SNAPSHOT.jar'
USER root
RUN addgroup --gid 2000 spring && adduser --uid 2000 --gid 2000 spring
USER spring:spring
COPY target/${JAR_NAME} app.jar
ENTRYPOINT ["java","-jar","/app.jar"]
